# General imports
import argparse
import logging
import signal

from helpers.config import Config
logging.basicConfig(level=logging.DEBUG if Config()["DEBUG"] else logging.INFO)

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
import prometheus_client

from common.db import dbConnector
from common.ddog import datadogClient
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
from handlers import seasonalHandler
from helpers import consoleHelper
from common import agpl
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

		(r"/web/osu-getseasonal.php", seasonalHandler.handler),

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


def main():
	parser = argparse.ArgumentParser(
		description=consoleHelper.ASCII + "\n\nLatest Essential Tatoe Server v{}\nBy The Ripple Team".format(
			glob.VERSION
		),
		formatter_class=argparse.RawTextHelpFormatter
	)
	parser.add_argument("-p", "--port", help="Run on a specific port (bypasses config.ini)", required=False)
	parser.add_argument("-s", "--stats-port", help="Run prometheus on a specific port (bypasses config.ini)", required=False)
	parser.add_argument("-q", "--quiet", help="Log less stuff during startup", required=False, default=False, action="store_true")
	cli_args = parser.parse_args()

	# AGPL license agreement
	try:
		agpl.check_license("ripple", "LETS")
	except agpl.LicenseError as e:
		logging.error(str(e))
		sys.exit(1)

	try:
		if not cli_args.quiet:
			consoleHelper.printServerStartHeader(True)

		def loudLog(s, f=logging.info):
			if not cli_args.quiet:
				f(s)

		# Read config
		loudLog("Reading config file... ")
		glob.conf = Config()

		# Create data/oppai maps folder if needed
		loudLog("Checking folders... ")
		paths = (
			".data",
			glob.conf["BEATMAPS_FOLDER"],
			glob.conf["SCREENSHOTS_FOLDER"],
			glob.conf["FAILED_REPLAYS_FOLDER"],
			glob.conf["REPLAYS_FOLDER"]
		)
		for i in paths:
			if not os.path.exists(i):
				os.makedirs(i, 0o770)

		# Connect to db
		try:
			loudLog("Connecting to MySQL database")
			glob.db = dbConnector.db(
				host=glob.conf["DB_HOST"],
				port=glob.conf["DB_PORT"],
				user=glob.conf["DB_USERNAME"],
				password=glob.conf["DB_PASSWORD"],
				database=glob.conf["DB_NAME"],
				autocommit=True,
				charset="utf8"
			)
			glob.db.fetch("SELECT 1")
		except:
			# Exception while connecting to db
			logging.error("Error while connection to database. Please check your config.ini and run the server again")
			raise

		# Connect to redis
		try:
			loudLog("Connecting to redis")
			glob.redis = redis.Redis(
				glob.conf["REDIS_HOST"],
				glob.conf["REDIS_PORT"],
				glob.conf["REDIS_DATABASE"],
				glob.conf["REDIS_PASSWORD"]
			)
			glob.redis.ping()
		except:
			# Exception while connecting to db
			logging.error("Error while connection to redis. Please check your config.ini and run the server again")
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
			loudLog("Creating threads pool")
			glob.pool = ThreadPool(glob.conf["THREADS"])
		except:
			logging.error("Error while creating threads pool. Please check your config.ini and run the server again")
			raise

		# Check osuapi
		if not glob.conf["OSU_API_ENABLE"]:
			logging.warning(
				"osu!api features are disabled. If you don't have a "
				"valid beatmaps table, all beatmaps will show as unranked"
			)
			if glob.conf["BEATMAP_CACHE_EXPIRE"] > 0:
				logging.warning(
					"IMPORTANT! Your beatmapcacheexpire in config.ini is > 0 and osu!api "
					"features are disabled.\nWe do not reccoment this, because too old "
					"beatmaps will be shown as unranked.\nSet beatmapcacheexpire to 0 to "
					"disable beatmap latest update check and fix that issue."
				)

		# Load achievements
		loudLog("Loading achievements")
		try:
			secret.achievements.utils.load_achievements()
		except:
			logging.error("Error while loading achievements")
			raise

		# Set achievements version
		glob.redis.set("lets:achievements_version", glob.ACHIEVEMENTS_VERSION)
		loudLog("Achievements version is {}".format(glob.ACHIEVEMENTS_VERSION))

		# Load AQL thresholds
		loudLog("Loading AQL thresholds")
		try:
			glob.aqlThresholds.reload()
		except:
			logging.error("Error while reloading AQL thresholds")
			raise

		# Check if s3 is enabled
		if not glob.conf.s3_enabled:
			loudLog("S3 is disabled!", logging.warning)
		else:
			c = glob.db.fetch("SELECT COUNT(*) AS c FROM s3_replay_buckets WHERE max_score_id IS NULL")["c"]
			if c != 1:
				logging.error(
					"There must be only one bucket flagged as WRITE bucket! You have {}.".format(c),
				)
				sys.exit()

		# Discord
		if glob.conf.schiavo_enabled:
			glob.schiavo = schiavo.schiavo(glob.conf["SCHIAVO_URL"], "**lets**")
		else:
			logging.warning("Schiavo logging is disabled!")

		# Server port
		try:
			if cli_args.port:
				loudLog("Running on port {}, bypassing config.ini".format(cli_args.port), logging.warning)
				glob.serverPort = int(cli_args.port)
			else:
				glob.serverPort = glob.conf["HTTP_PORT"]
		except:
			logging.error("Invalid server port! Please check your config.ini and run the server again")
			raise

		# Prometheus port
		try:
			if cli_args.stats_port:
				loudLog("Running stats exporter on port {}, bypassing config.ini".format(cli_args.stats_port), logging.warning)
				glob.statsPort = int(cli_args.stats_port)
			elif glob.conf["PROMETHEUS_PORT"]:
				glob.statsPort = int(glob.conf["PROMETHEUS_PORT"])
		except:
			logging.error("Invalid stats port! Please check your config.ini and run the server again")
			raise

		# Make app
		glob.application = make_app()

		# Set up sentry
		if glob.conf.sentry_enabled:
			glob.application.sentry_client = AsyncSentryClient(glob.conf["SENTRY_DSN"], release=glob.VERSION)
		else:
			loudLog("Sentry logging is disabled!", logging.warning)

		# Set up Datadog
		if glob.conf.datadog_enabled:
			glob.dog = datadogClient.datadogClient(
				glob.conf["DATADOG_API_KEY"],
				glob.conf["DATADOG_APP_KEY"],
				constant_tags=["worker:{}".format(glob.serverPort)]
			)
		else:
			glob.dog = datadogClient.datadogClient()
			loudLog("Datadog stats tracking is disabled!", logging.warning)

		# Connect to pubsub channels
		t = pubSub.listener(glob.redis, {
			"lets:beatmap_updates": beatmapUpdateHandler.handler(),
			"lets:reload_aql": lambda x: x == b"reload" and glob.aqlThresholds.reload(),
		})
		t.setDaemon(True)
		t.start()

		# Check debug mods
		if glob.conf["DEBUG"]:
			logging.warning("Server running in debug mode.")

		# Close main thread db connection as we don't need it anymore
		glob.threadScope.dbClose()

		# Server start message and console output
		logging.info("L.E.T.S. is listening for clients on {}:{}...".format(
			glob.conf["HTTP_HOST"],
			glob.serverPort
		))
		# log.discord("bunker", "Server started!")

		# Start Tornado
		def term(_, __):
			tornado.ioloop.IOLoop.instance().add_callback_from_signal(
				lambda: tornado.ioloop.IOLoop.instance().stop()
			)

		signal.signal(signal.SIGINT, term)
		signal.signal(signal.SIGTERM, term)
		if glob.statsPort is not None:
			logging.info("Stats exporter listening on 0.0.0.0:{}".format(glob.statsPort))
			prometheus_client.start_http_server(glob.statsPort, addr="0.0.0.0")
		glob.application.listen(glob.serverPort, address=glob.conf["HTTP_HOST"])
		tornado.ioloop.IOLoop.instance().start()
		logging.debug("IOLoop stopped")
	finally:
		# Perform some clean up
		logging.info("Disposing server")
		glob.fileBuffers.flushAll()
		if glob.redis.connection_pool is not None:
			glob.redis.connection_pool.disconnect()
		# TODO: properly dispose mysql connections
		if glob.pool is not None:
			# Close db conn in each thread
			glob.pool.imap(lambda *_: glob.threadScope.dbClose(), [None] * glob.conf["THREADS"], chunksize=1)
			# Wait for everything else to finish (should always terminate immediately)
			glob.pool.close()
			glob.pool.join()
		logging.info("Goodbye!")
		# sys.exit(0)


if __name__ == "__main__":
	main()
