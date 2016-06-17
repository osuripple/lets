import beatmap
import scoreboard
import glob
from constants import exceptions
from helpers import requestHelper
from helpers import discordBotHelper
from helpers import userHelper
import sys
import traceback
from helpers import logHelper as log

# Exception tracking
import tornado.web
import tornado.gen
from raven.contrib.tornado import SentryMixin

MODULE_NAME = "get_scores"
class handler(SentryMixin, requestHelper.asyncRequestHandler):
	"""
	Handler for /web/osu-osz2-getscores.php
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self):
		try:
			# Get request ip
			ip = self.getRequestIP()

			# Print arguments
			if glob.debug == True:
				requestHelper.printArguments(self)

			# TODO: Maintenance check

			# Check required arguments
			if requestHelper.checkArguments(self.request.arguments, ["c", "f", "i", "m", "us"]) == False:
				raise exceptions.invalidArgumentsException(MODULE_NAME)

			# GET parameters
			md5 = self.get_argument("c")
			fileName = self.get_argument("f")
			beatmapSetID = self.get_argument("i")
			gameMode = self.get_argument("m")
			username = self.get_argument("us")
			password = self.get_argument("ha")

			# Login and ban check
			userID = userHelper.getID(username)
			if userID == 0:
				raise exceptions.loginFailedException(MODULE_NAME, userID)
			if userHelper.checkLogin(userID, password, ip) == False:
				raise exceptions.loginFailedException(MODULE_NAME, username)
			if userHelper.getAllowed(userID) == 0:
				raise exceptions.userBannedException(MODULE_NAME, username)

			# Hax check
			if "a" in self.request.arguments:
				if int(self.get_argument("a")) == 1 and not userHelper.getAqn(userID):
					log.warning("Found AQN folder on user {} ({})".format(username, userID), True)
					userHelper.setAqn(userID)

			# Console output
			fileNameShort = fileName[:32]+"..." if len(fileName) > 32 else fileName[:-4]
			log.info("Requested beatmap {} ({})".format(fileNameShort, md5))

			# Create beatmap object and set its data
			bmap = beatmap.beatmap(md5, beatmapSetID)

			# Create leaderboard object, link it to bmap and get all scores
			sboard = scoreboard.scoreboard(username, gameMode, bmap)

			# Data to return
			data = ""
			data += bmap.getData()
			data += sboard.getScoresData()
			self.write(data)
		except exceptions.invalidArgumentsException:
			self.write("error: meme")
		except exceptions.userBannedException:
			self.write("error: ban")
		except exceptions.loginFailedException:
			self.write("error: pass")
		except:
			log.error("Unknown error!\n```\n{}\n{}```".format(sys.exc_info(), traceback.format_exc()))
			if glob.sentry:
				yield tornado.gen.Task(self.captureException, exc_info=True)
		#finally:
		#	self.finish()
