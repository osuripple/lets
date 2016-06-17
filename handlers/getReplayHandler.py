import os
from helpers import requestHelper
from helpers import userHelper
from constants import exceptions
import glob
import sys
import traceback
from helpers import logHelper as log
from helpers.exceptionsTracker import trackExceptions

# Exception tracking
import tornado.web
import tornado.gen
from raven.contrib.tornado import SentryMixin

MODULE_NAME = "get_replay"
class handler(SentryMixin, requestHelper.asyncRequestHandler):
	"""
	Handler for osu-getreplay.php
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self):
		try:
			# Get request ip
			ip = self.getRequestIP()

			# Check arguments
			if requestHelper.checkArguments(self.request.arguments, ["c", "u", "h"]) == False:
				raise exceptions.invalidArgumentsException(MODULE_NAME)

			# Get arguments
			username = self.get_argument("u")
			password = self.get_argument("h")
			replayID = self.get_argument("c")

			# Login check
			userID = userHelper.getID(username)
			if userID == 0:
				raise exceptions.loginFailedException(MODULE_NAME, userID)
			if userHelper.checkLogin(userID, password, ip) == False:
				raise exceptions.loginFailedException(MODULE_NAME, username)

			# Get user ID
			replayData = glob.db.fetch("SELECT scores.*, users.username AS uname FROM scores LEFT JOIN users ON scores.userid = users.id WHERE scores.id = %s", [replayID])

			# Increment 'replays watched by others' if needed
			if replayData != None:
				if username != replayData["uname"]:
					userHelper.incrementReplaysWatched(replayData["userid"], replayData["play_mode"])

			# Serve replay
			log.info("Serving replay_{}.osr".format(replayID))
			fileName = ".data/replays/replay_{}.osr".format(replayID)
			if os.path.isfile(fileName):
				with open(fileName, "rb") as f:
					fileContent = f.read()
				self.write(fileContent)
			else:
				log.warning("Replay {} doesn't exist".format(replayID))
				self.write("")
		except exceptions.invalidArgumentsException:
			pass
		except exceptions.loginFailedException:
			pass
		except:
			log.error("Unknown error in {}!\n```{}\n{}```".format(MODULE_NAME, sys.exc_info(), traceback.format_exc()))
			if glob.sentry:
				yield tornado.gen.Task(self.captureException, exc_info=True)
		#finally:
		#	self.finish()
