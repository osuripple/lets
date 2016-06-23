# General imports
import sys
import os
import glob
from helpers import consoleHelper
from helpers import databaseHelperNew
from helpers import config
from helpers import generalHelper
from helpers import userHelper
from constants import bcolors
from helpers import logHelper as log
from multiprocessing.pool import ThreadPool

# Handlers
from handlers import getScoresHandler
from handlers import submitModularHandler
from handlers import banchoConnectHandler
from handlers import getReplayHandler
from handlers import mapsHandler
from handlers import uploadScreenshotHandler
from handlers import getScreenshotHandler
from handlers import osuSearchHandler
from handlers import osuSearchSetHandler
from handlers import apiStatusHandler
from handlers import apiPPHandler
from handlers import downloadMapHandler
from handlers import getFullReplayHandler

from handlers import redirectHandler

# Tornado
import tornado.ioloop
import tornado.web
import tornado.httpserver
import tornado.gen

# Raven
from raven.contrib.tornado import AsyncSentryClient

def make_app():
	return tornado.web.Application([
		(r"/web/bancho_connect.php", banchoConnectHandler.handler),
		(r"/web/osu-osz2-getscores.php", getScoresHandler.handler),
		(r"/web/osu-submit-modular.php", submitModularHandler.handler),
		(r"/web/osu-getreplay.php", getReplayHandler.handler),
		(r"/web/osu-screenshot.php", uploadScreenshotHandler.handler),
		(r"/web/osu-search.php", osuSearchHandler.handler),
		(r"/web/osu-search-set.php", osuSearchSetHandler.handler),
		(r"/ss/(.*)", getScreenshotHandler.handler),
		(r"/web/maps/(.*)", mapsHandler.handler),
		(r"/d/(.*)", downloadMapHandler.handler),
		(r"/s/(.*)", downloadMapHandler.handler),
		(r"/web/replays/(.*)", getFullReplayHandler.handler),

		(r"/p/verify", redirectHandler.handler, dict(destination="https://ripple.moe/index.php?p=2")),
		(r"/u/(.*)", redirectHandler.handler, dict(destination="https://ripple.moe/index.php?u={}")),

		(r"/api/v1/status", apiStatusHandler.handler),
		(r"/api/v1/pp", apiPPHandler.handler),
	])

if __name__ == "__main__":
	consoleHelper.printServerStartHeader(True)

	# Read config
	consoleHelper.printNoNl("> Reading config file... ")
	glob.conf = config.config("config.ini")

	if glob.conf.default == True:
		# We have generated a default config.ini, quit server
		consoleHelper.printWarning()
		consoleHelper.printColored("[!] config.ini not found. A default one has been generated.", bcolors.YELLOW)
		consoleHelper.printColored("[!] Please edit your config.ini and run the server again.", bcolors.YELLOW)
		sys.exit()

	# If we haven't generated a default config.ini, check if it's valid
	if glob.conf.checkConfig() == False:
		consoleHelper.printError()
		consoleHelper.printColored("[!] Invalid config.ini. Please configure it properly", bcolors.RED)
		consoleHelper.printColored("[!] Delete your config.ini to generate a default one", bcolors.RED)
		sys.exit()
	else:
		consoleHelper.printDone()

	# Check oppai
	consoleHelper.printNoNl("> Checking oppai... ")
	if os.path.isfile("../oppai/oppai") or os.path.isfile("../oppai/oppai.exe"):
		consoleHelper.printDone()
	else:
		consoleHelper.printError()
		consoleHelper.printColored("[!] Oppai not found! Please put oppai(.exe) in {}/oppai/oppai(.exe) and run LETS again.".format(os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))), bcolors.YELLOW)
		consoleHelper.printColored("[!] You can download oppai's source here -> {}https://github.com/osuripple/oppai".format(bcolors.UNDERLINE), bcolors.YELLOW)
		sys.exit()

	# Create data/oppai maps folder if needed
	consoleHelper.printNoNl("> Checking folders... ")
	paths = [".data", ".data/replays", ".data/screenshots", "../oppai", "../oppai/maps"]
	for i in paths:
		if not os.path.exists(i):
			os.makedirs(i, 0o770)
	consoleHelper.printDone()

	# Connect to db
	try:
		consoleHelper.printNoNl("> Connecting to db with MySQLdb")
		glob.db = databaseHelperNew.db(glob.conf.config["db"]["host"], glob.conf.config["db"]["username"], glob.conf.config["db"]["password"], glob.conf.config["db"]["database"], int(glob.conf.config["db"]["workers"]))
		consoleHelper.printNoNl(" ")
		consoleHelper.printDone()
	except:
		# Exception while connecting to db
		consoleHelper.printError()
		consoleHelper.printColored("[!] Error while connection to database. Please check your config.ini and run the server again", bcolors.RED)
		raise

	# Create threads pool
	try:
		consoleHelper.printNoNl("> Creating threads pool... ")
		glob.pool = ThreadPool(int(glob.conf.config["server"]["threads"]))
		consoleHelper.printDone()
	except:
		consoleHelper.printError()
		consoleHelper.printColored("[!] Error while creating threads pool. Please check your config.ini and run the server again", bcolors.RED)

	# Check osuapi
	if generalHelper.stringToBool(glob.conf.config["osuapi"]["enable"]) == False:
		consoleHelper.printColored("[!] osu!api features are disabled. If you don't have a valid beatmaps table, all beatmaps will show as unranked", bcolors.YELLOW)
		if int(glob.conf.config["server"]["beatmapcacheexpire"]) > 0:
			consoleHelper.printColored("[!] IMPORTANT! Your beatmapcacheexpire in config.ini is > 0 and osu!api features are disabled.\nWe do not reccoment this, because too old beatmaps will be shown as unranked.\nSet beatmapcacheexpire to 0 to disable beatmap latest update check and fix that issue.", bcolors.YELLOW)

	# Discord
	glob.discord = generalHelper.stringToBool(glob.conf.config["discord"]["enable"])
	if glob.discord == False:
		consoleHelper.printColored("[!] Warning! Discord logging is disabled!", bcolors.YELLOW)

	# Check debug mods
	glob.debug = generalHelper.stringToBool(glob.conf.config["server"]["debug"])
	if glob.debug == True:
		consoleHelper.printColored("[!] Warning! Server running in debug mode!", bcolors.YELLOW)

	# Server port
	try:
		serverPort = int(glob.conf.config["server"]["port"])
	except:
		consoleHelper.printColored("[!] Invalid server port! Please check your config.ini and run the server again", bcolors.RED)

	# Make app
	application = make_app()

	# Set up sentry
	try:
		glob.sentry = generalHelper.stringToBool(glob.conf.config["sentry"]["enable"])
		if glob.sentry == True:
			application.sentry_client = AsyncSentryClient(glob.conf.config["sentry"]["dns"], release=glob.VERSION)
		else:
			consoleHelper.printColored("[!] Warning! Sentry logging is disabled!", bcolors.YELLOW)
	except:
		consoleHelper.printColored("[!] Error while starting sentry client! Please check your config.ini and run the server again", bcolors.RED)

	# Cloudflare meme
	glob.cloudflare = generalHelper.stringToBool(glob.conf.config["server"]["cloudflare"])

	# Cache user ids
	consoleHelper.printNoNl("> Caching user IDs... ")
	userHelper.cacheUserIDs()
	consoleHelper.printDone()

	# Server start message and console output
	consoleHelper.printColored("> L.E.T.S. is listening for clients on 127.0.0.1:{}...".format(serverPort), bcolors.GREEN)
	log.logMessage("Server started!", discord=True, of="info.txt", stdout=False)

	# Start Tornado
	application.listen(serverPort)
	tornado.ioloop.IOLoop.instance().start()
