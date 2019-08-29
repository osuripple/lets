import timeout_decorator
import tornado.gen
import tornado.web

from common.log import logUtils as log
from common.ripple import userUtils
from common.web import requestsManager
from constants import exceptions
from helpers import replayHelper
from objects import glob
from common.sentry import sentry

MODULE_NAME = "get_replay"
class handler(requestsManager.asyncRequestHandler):
	"""
	Handler for osu-getreplay.php
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	@sentry.captureTornado
	def asyncGet(self):
		try:
			# Get request ip
			ip = self.getRequestIP()

			# Check arguments
			if not requestsManager.checkArguments(self.request.arguments, ["c", "u", "h"]):
				raise exceptions.invalidArgumentsException(MODULE_NAME)

			# Get arguments
			username = self.get_argument("u")
			password = self.get_argument("h")
			replayID = self.get_argument("c")

			# Login check
			userID = userUtils.getID(username)
			if userID == 0:
				raise exceptions.loginFailedException(MODULE_NAME, userID)
			if not userUtils.checkLogin(userID, password, ip):
				raise exceptions.loginFailedException(MODULE_NAME, username)
			if userUtils.check2FA(userID, ip):
				raise exceptions.need2FAException(MODULE_NAME, username, ip)

			# Get user ID
			replayData = glob.db.fetch("SELECT scores.*, users.username AS uname FROM scores LEFT JOIN users ON scores.userid = users.id WHERE scores.id = %s", [replayID])

			# Increment 'replays watched by others' if needed
			if replayData is not None:
				if username != replayData["uname"]:
					userUtils.incrementReplaysWatched(replayData["userid"], replayData["play_mode"])

			# Serve replay
			log.info("Serving replay_{}.osr".format(replayID))
			r = ""
			replayID = int(replayID)
			try:
				r = replayHelper.getRawReplayS3(replayID)
			except timeout_decorator.TimeoutError:
				log.warning("S3 timed out")
				sentry.captureMessage("S3 timeout while fetching replay.")
			except FileNotFoundError:
				log.warning("Replay {} doesn't exist".format(replayID))
			finally:
				self.write(r)
		except exceptions.invalidArgumentsException:
			pass
		except exceptions.need2FAException:
			pass
		except exceptions.loginFailedException:
			pass