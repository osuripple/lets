import sys
import traceback

import tornado.gen
import tornado.web
from raven.contrib.tornado import SentryMixin

import beatmap
import scoreboard
from common.constants import privileges
from common.log import logUtils as log
from common.ripple import userUtils
from common.web import requestsManager
from constants import exceptions
from objects import glob

MODULE_NAME = "get_scores"
class handler(SentryMixin, requestsManager.asyncRequestHandler):
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
			if glob.debug:
				requestsManager.printArguments(self)

			# TODO: Maintenance check

			# Check required arguments
			if not requestsManager.checkArguments(self.request.arguments, ["c", "f", "i", "m", "us", "v", "mods"]):
				raise exceptions.invalidArgumentsException(MODULE_NAME)

			# GET parameters
			md5 = self.get_argument("c")
			fileName = self.get_argument("f")
			beatmapSetID = self.get_argument("i")
			gameMode = self.get_argument("m")
			username = self.get_argument("us")
			password = self.get_argument("ha")
			scoreboardType = int(self.get_argument("v"))

			# Login and ban check
			userID = userUtils.getID(username)
			if userID == 0:
				raise exceptions.loginFailedException(MODULE_NAME, userID)
			if not userUtils.checkLogin(userID, password, ip):
				raise exceptions.loginFailedException(MODULE_NAME, username)
			# Ban check is pointless here, since there's no message on the client
			#if userHelper.isBanned(userID) == True:
			#	raise exceptions.userBannedException(MODULE_NAME, username)

			# Hax check
			if "a" in self.request.arguments:
				if int(self.get_argument("a")) == 1 and not userUtils.getAqn(userID):
					log.warning("Found AQN folder on user {} ({})".format(username, userID), "cm")
					userUtils.setAqn(userID)

			# Scoreboard type
			country = False
			friends = False
			mods = -1
			if scoreboardType == 4:
				# Country leaderboard
				country = True
			elif scoreboardType == 2:
				# Mods leaderboard, replace mods (-1, every mod) with "mods" GET parameters
				mods = int(self.get_argument("mods"))
			elif scoreboardType == 3 and userUtils.getPrivileges(userID) & privileges.USER_DONOR > 0:
				# Friends leaderboard
				friends = True

			# Console output
			fileNameShort = fileName[:32]+"..." if len(fileName) > 32 else fileName[:-4]
			log.info("Requested beatmap {} ({})".format(fileNameShort, md5))

			# Create beatmap object and set its data
			bmap = beatmap.beatmap(md5, beatmapSetID, gameMode)

			# Create leaderboard object, link it to bmap and get all scores
			sboard = scoreboard.scoreboard(username, gameMode, bmap, setScores=True, country=country, mods=mods, friends=friends)

			# Data to return
			data = ""
			data += bmap.getData(sboard.totalScores)
			data += sboard.getScoresData()
			self.write(data)

			# Datadog stats
			glob.dog.increment(glob.DATADOG_PREFIX+".served_leaderboards")
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
