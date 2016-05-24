# General imports
import sys
import os
import glob
from helpers import consoleHelper
from helpers import databaseHelperNew
from helpers import config
from helpers import generalHelper
from constants import bcolors
from helpers import discordBotHelper

# Handlers
from handlers import getScoresHandler
from handlers import submitModularHandler
from handlers import banchoConnectHandler
from handlers import getReplayHandler
from handlers import mapsHandler
from handlers import uploadScreenshotHandler
from handlers import getScreenshotHandler
from handlers import osuSearchHandler

from handlers import apiStatusHandler
from handlers import apiPPHandler

# Tornado
import tornado.ioloop
import tornado.web
import tornado.httpserver
import tornado.gen

from tornado.ioloop import IOLoop
from multiprocessing.pool import ThreadPool

pool = ThreadPool(10)

def run_background(func, callback, args=(), kwargs={}):
	def _callback(result):
		IOLoop.instance().add_callback(lambda: callback(result))
	pool.apply_async(func, args, kwargs, _callback)

def blocking_task():
	for i in range(1,10000):
		res = glob.db.fetch("SELECT * FROM scores WHERE id = %s", [i])
		print(str(res))

class blockingHandler(tornado.web.RequestHandler):
	@tornado.web.asynchronous
	@tornado.gen.engine
	def get(self):
		print("Blocking request")
		yield tornado.gen.Task(run_background, blocking_task)
		self.write("ok")
		self.finish()

class AsyncHandler(tornado.web.RequestHandler):
	@tornado.web.asynchronous
	def get(self):
		print("Async request")
		self.write("yee")
		self.finish()

def make_app():
	return tornado.web.Application([
		(r"/web/bancho_connect.php", banchoConnectHandler.handler),
		(r"/web/osu-osz2-getscores.php", getScoresHandler.handler),
		(r"/web/osu-submit-modular.php", submitModularHandler.handler),
		(r"/web/osu-getreplay.php", getReplayHandler.handler),
		(r"/web/osu-screenshot.php", uploadScreenshotHandler.handler),
		(r"/web/osu-search.php", osuSearchHandler.handler),
		(r"/ss/(.*)", getScreenshotHandler.handler),
		(r"/web/maps/(.*)", mapsHandler.handler),

		(r"/api/v1/status", apiStatusHandler.handler),
		(r"/api/v1/pp", apiPPHandler.handler),

		(r"/blocking", blockingHandler),
		(r"/async", AsyncHandler)
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

	# Connect to db
	try:
		print("> Connecting to db with MySQLdb... ")
		glob.db = databaseHelperNew.db(glob.conf.config["db"]["host"], glob.conf.config["db"]["username"], glob.conf.config["db"]["password"], glob.conf.config["db"]["database"])
		consoleHelper.printDone()
	except:
		# Exception while connecting to db
		consoleHelper.printError()
		consoleHelper.printColored("[!] Error while connection to database. Please check your config.ini and run the server again", bcolors.RED)
		raise

	# Create data folder if needed
	consoleHelper.printNoNl("> Checking folders... ")
	paths = [".data", ".data/replays", ".data/screenshots"]
	for i in paths:
		if not os.path.exists(i):
			os.makedirs(i, 0o770)
	consoleHelper.printDone()

	# Enable PP if this is the officialTM ripple server
	if os.path.isfile("rippoppai.py"):
		glob.pp = True
		print("> Using {}rippoppai{} as PP calculator.".format(bcolors.GREEN, bcolors.ENDC))
	else:
		consoleHelper.printColored("[!] No PP calculator found. PP are disabled.", bcolors.YELLOW)

	# Check osuapi
	if generalHelper.stringToBool(glob.conf.config["osuapi"]["enable"]) == False:
		consoleHelper.printColored("[!] osu!api features are disabled. If you don't have a valid beatmaps table, all beatmaps will show as unranked", bcolors.YELLOW)
		if int(glob.conf.config["server"]["beatmapcacheexpire"]) > 0:
			consoleHelper.printColored("[!] IMPORTANT! Your beatmapcacheexpire in config.ini is > 0 and osu!api features are disabled.\nWe do not reccoment this, because too old beatmaps will be shown as unranked.\nSet beatmapcacheexpire to 0 to disable beatmap latest update check and fix that issue.", bcolors.YELLOW)

	# Check debug mods
	glob.debug = generalHelper.stringToBool(glob.conf.config["server"]["debug"])
	if glob.debug == True:
		consoleHelper.printColored("[!] LETS is running in debug mode.", bcolors.YELLOW)

	# Start the server
	discordBotHelper.sendConfidential("TATOE! (lets started)")

	serverPort = int(glob.conf.config["server"]["port"])
	consoleHelper.printColored("> L.E.T.S. is listening for clients on 127.0.0.1:{}...".format(serverPort), bcolors.GREEN)
	app = tornado.httpserver.HTTPServer(make_app())
	app.listen(serverPort)
	tornado.ioloop.IOLoop.instance().start()
