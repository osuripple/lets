# General imports
import argparse

import os
import sys
from multiprocessing.pool import ThreadPool

import tornado.gen
import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.netutil
from raven.contrib.tornado import AsyncSentryClient
import redis

from common.constants import bcolors
from common.db import dbConnector
from common.ddog import datadogClient
from common.log import logUtils as log
from common.redis import pubSub
from common.web import schiavo
from handlers import apiCacheBeatmapHandler, rateHandler, changelogHandler
from handlers import apiPPHandler
from handlers import apiStatusHandler
from handlers import banchoConnectHandler
from handlers import checkUpdatesHandler
from handlers import defaultHandler
from handlers import downloadMapHandler
from handlers import emptyHandler
from handlers import getFullReplayHandler
from handlers import getReplayHandler
from handlers import getScoresHandler
from handlers import getScreenshotHandler
from handlers import loadTestHandler
from handlers import mapsHandler
from handlers import osuErrorHandler
from handlers import osuSearchHandler
from handlers import osuSearchSetHandler
from handlers import redirectHandler
from handlers import submitModularHandler
from handlers import uploadScreenshotHandler
from handlers import commentHandler
from helpers import config
from helpers import consoleHelper
from common import generalUtils
from common import agpl
from helpers.config import Config
from objects import glob
from pubSubHandlers import beatmapUpdateHandler
import secret.achievements.utils


def make_app():
	return tornado.web.Application([
		(r"/web/bancho_connect.php", banchoConnectHandler.handler),
		(r"/web/osu-osz2-getscores.php", getScoresHandler.handler),
		(r"/web/osu-submit-modular.php", submitModularHandler.handler),
		(r"/web/osu-submit-modular-selector.php", submitModularHandler.handler),
		(r"/web/osu-getreplay.php", getReplayHandler.handler),
		(r"/web/osu-screenshot.php", uploadScreenshotHandler.handler),
		(r"/web/osu-search.php", osuSearchHandler.handler),
		(r"/web/osu-search-set.php", osuSearchSetHandler.handler),
		(r"/web/check-updates.php", checkUpdatesHandler.handler),
		(r"/web/osu-error.php", osuErrorHandler.handler),
		(r"/web/osu-comment.php", commentHandler.handler),
		(r"/web/osu-rate.php", rateHandler.handler),
        (r"/p/changelog", changelogHandler.handler),
		(r"/ss/(.*)", getScreenshotHandler.handler),
		(r"/web/maps/(.*)", mapsHandler.handler),
		(r"/d/(.*)", downloadMapHandler.handler),
		(r"/s/(.*)", downloadMapHandler.handler),
		(r"/web/replays/(.*)", getFullReplayHandler.handler),

		(r"/p/verify", redirectHandler.handler, dict(destination="https://ripple.moe/index.php?p=2")),
		(r"/u/(.*)", redirectHandler.handler, dict(destination="https://ripple.moe/index.php?u={}")),

		(r"/api/v1/status", apiStatusHandler.handler),
		(r"/api/v1/pp", apiPPHandler.handler),
		(r"/api/v1/cacheBeatmap", apiCacheBeatmapHandler.handler),

		(r"/letsapi/v1/status", apiStatusHandler.handler),
		(r"/letsapi/v1/pp", apiPPHandler.handler),
		(r"/letsapi/v1/cacheBeatmap", apiCacheBeatmapHandler.handler),

		# Not done yet
		(r"/web/lastfm.php", emptyHandler.handler),
		(r"/web/osu-checktweets.php", emptyHandler.handler),
		(r"/web/osu-addfavourite.php", emptyHandler.handler),

		(r"/loadTest", loadTestHandler.handler),
	], default_handler_class=defaultHandler.handler)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description=consoleHelper.ASCII + "\n\nLatest Essential Tatoe Server v{}\nBy The Ripple Team".format(
			glob.VERSION
		),
		formatter_class=argparse.RawTextHelpFormatter
	)
	parser.add_argument("-p", "--port", help="Run on a specific port (bypasses config.ini)", required=False)
	cli_args = parser.parse_args()

	# AGPL license agreement
	try:
		agpl.check_license("ripple", "LETS")
	except agpl.LicenseError as e:
		print(str(e))
		sys.exit(1)

	try:
		consoleHelper.printServerStartHeader(True)

		# Read config
		consoleHelper.printNoNl("> Reading config file... ")
		glob.conf = Config()

		# if glob.conf.default:
			# We have generated a default config.ini, quit server
			# consoleHelper.printWarning()
			# consoleHelper.printColored("[!] config.ini not found. A default one has been generated.", bcolors.YELLOW)
			# consoleHelper.printColored("[!] Please edit your config.ini and run the server again.", bcolors.YELLOW)
			# sys.exit()

		# If we haven't generated a default config.ini, check if it's valid
		# if not glob.conf.checkConfig():
		# 	consoleHelper.printError()
		# 	consoleHelper.printColored("[!] Invalid config.ini. Please configure it properly", bcolors.RED)
		# 	consoleHelper.printColored("[!] Delete your config.ini to generate a default one", bcolors.RED)
		# 	sys.exit()
		# else:
		# 	consoleHelper.printDone()

		# Create data/oppai maps folder if needed
		consoleHelper.printNoNl("> Checking folders... ")
		paths = [
			".data",
			".data/oppai",
			".data/catch_the_pp",
			glob.conf["BEATMAPS_FOLDER"],
			glob.conf["SCREENSHOTS_FOLDER"]
		] + glob.conf["REPLAYS_FOLDERS"]
		for i in paths:
			if not os.path.exists(i):
				os.makedirs(i, 0o770)
		consoleHelper.printDone()

		# Connect to db
		try:
			consoleHelper.printNoNl("> Connecting to MySQL database... ")
			glob.db = dbConnector.db(
				glob.conf["DB_HOST"],
				glob.conf["DB_PORT"],
				glob.conf["DB_USERNAME"],
				glob.conf["DB_PASSWORD"],
				glob.conf["DB_NAME"],
				glob.conf["DB_WORKERS"]
			)
			consoleHelper.printNoNl(" ")
			consoleHelper.printDone()
		except:
			# Exception while connecting to db
			consoleHelper.printError()
			consoleHelper.printColored("[!] Error while connection to database. Please check your config.ini and run the server again", bcolors.RED)
			raise

		# Connect to redis
		try:
			consoleHelper.printNoNl("> Connecting to redis... ")
			glob.redis = redis.Redis(
				glob.conf["REDIS_HOST"],
				glob.conf["REDIS_PORT"],
				glob.conf["REDIS_DATABASE"],
				glob.conf["REDIS_PASSWORD"]
			)
			glob.redis.ping()
			consoleHelper.printNoNl(" ")
			consoleHelper.printDone()
		except:
			# Exception while connecting to db
			consoleHelper.printError()
			consoleHelper.printColored("[!] Error while connection to redis. Please check your config.ini and run the server again", bcolors.RED)
			raise

		# Empty redis cache
		try:
			glob.redis.eval("return redis.call('del', unpack(redis.call('keys', ARGV[1])))", 0, "lets:*")
		except redis.exceptions.ResponseError:
			# Script returns error if there are no keys starting with peppy:*
			pass

		# Save lets version in redis
		glob.redis.set("lets:version", glob.VERSION)

		# Create threads pool
		try:
			consoleHelper.printNoNl("> Creating threads pool... ")
			glob.pool = ThreadPool(glob.conf["THREADS"])
			consoleHelper.printDone()
		except:
			consoleHelper.printError()
			consoleHelper.printColored("[!] Error while creating threads pool. Please check your config.ini and run the server again", bcolors.RED)

		# Check osuapi
		if not glob.conf["OSU_API_ENABLE"]:
			consoleHelper.printColored("[!] osu!api features are disabled. If you don't have a valid beatmaps table, all beatmaps will show as unranked", bcolors.YELLOW)
			if glob.conf["BEATMAP_CACHE_EXPIRE"] > 0:
				consoleHelper.printColored("[!] IMPORTANT! Your beatmapcacheexpire in config.ini is > 0 and osu!api features are disabled.\nWe do not reccoment this, because too old beatmaps will be shown as unranked.\nSet beatmapcacheexpire to 0 to disable beatmap latest update check and fix that issue.", bcolors.YELLOW)

		# Load achievements
		consoleHelper.printNoNl("Loading achievements... ")
		try:
			secret.achievements.utils.load_achievements()
		except Exception as e:
			consoleHelper.printError()
			consoleHelper.printColored(
				"[!] Error while loading achievements! ({})".format(e),
				bcolors.RED,
			)
			sys.exit()
		consoleHelper.printDone()

		# Set achievements version
		glob.redis.set("lets:achievements_version", glob.ACHIEVEMENTS_VERSION)
		consoleHelper.printColored("Achievements version is {}".format(glob.ACHIEVEMENTS_VERSION), bcolors.YELLOW)

		# Load AQL thresholds
		print("Loading AQL thresholds... ")
		try:
			glob.aqlThresholds.reload()
		except Exception as e:
			consoleHelper.printError()
			consoleHelper.printColored("[!] {}".format(e), bcolors.RED,)
			sys.exit()
		consoleHelper.printDone()

		# Discord
		if glob.conf.schiavo_enabled:
			glob.schiavo = schiavo.schiavo(glob.conf["SCHIAVO_URL"], "**lets**")
		else:
			consoleHelper.printColored("[!] Warning! Schiavo logging is disabled!", bcolors.YELLOW)

		# Server port
		try:
			if cli_args.port:
				consoleHelper.printColored("[!] Running on port {}, bypassing config.ini", bcolors.YELLOW)
				glob.serverPort = int(cli_args.port)
			else:
				glob.serverPort = glob.conf["HTTP_PORT"]
		except:
			consoleHelper.printColored("[!] Invalid server port! Please check your config.ini and run the server again", bcolors.RED)

		# Make app
		glob.application = make_app()

		# Set up sentry
		try:
			if glob.conf.sentry_enabled:
				glob.application.sentry_client = AsyncSentryClient(glob.conf["SENTRY_DSN"], release=glob.VERSION)
			else:
				consoleHelper.printColored("[!] Warning! Sentry logging is disabled!", bcolors.YELLOW)
		except:
			consoleHelper.printColored("[!] Error while starting Sentry client! Please check your config.ini and run the server again", bcolors.RED)

		# Set up Datadog
		try:
			if glob.conf.datadog_enabled:
				glob.dog = datadogClient.datadogClient(
					glob.conf["DATADOG_API_KEY"],
					glob.conf["DATADOG_APP_KEY"],
					constant_tags=["worker:{}".format(glob.serverPort)]
				)
			else:
				consoleHelper.printColored("[!] Warning! Datadog stats tracking is disabled!", bcolors.YELLOW)
		except:
			consoleHelper.printColored("[!] Error while starting Datadog client! Please check your config.ini and run the server again", bcolors.RED)

		# Connect to pubsub channels
		pubSub.listener(glob.redis, {
			"lets:beatmap_updates": beatmapUpdateHandler.handler(),
			"lets:reload_aql": lambda x: x == b"reload" and glob.aqlThresholds.reload(),
		}).start()

		# Check debug mods
		if glob.conf["DEBUG"]:
			consoleHelper.printColored("[!] Server running in debug mode.", bcolors.RED)

		# Server start message and console output
		consoleHelper.printColored("> L.E.T.S. is listening for clients on {}:{}...".format(
			glob.conf["HTTP_HOST"],
			glob.serverPort
		), bcolors.GREEN)
		log.logMessage("Server started!", discord="bunker", stdout=False)

		# Start Tornado
		glob.application.listen(glob.serverPort, address=glob.conf["HTTP_HOST"])
		tornado.ioloop.IOLoop.instance().start()
	finally:
		# Perform some clean up
		print("> Disposing server... ")
		glob.fileBuffers.flushAll()
		consoleHelper.printColored("Goodbye!", bcolors.GREEN)
