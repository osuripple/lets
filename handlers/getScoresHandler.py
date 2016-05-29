import beatmap
import scoreboard
import glob
from helpers import consoleHelper
from constants import bcolors
from constants import exceptions
from helpers import requestHelper
from helpers import discordBotHelper
from helpers import userHelper
import sys
import traceback

MODULE_NAME = "get_scores"
class handler(requestHelper.asyncRequestHandler):
	"""
	Handler for /web/osu-osz2-getscores.php
	"""
	def asyncGet(self):
		try:
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
			if userHelper.checkLogin(userID, password) == False:
				raise exceptions.loginFailedException(MODULE_NAME, username)
			if userHelper.getAllowed(userID) == 0:
				raise exceptions.userBannedException(MODULE_NAME, username)

			# Hax check
			if "a" in self.request.arguments:
				if int(self.get_argument("a")) == 1 and not userHelper.getAqn(userID):
					discordBotHelper.sendConfidential("Found AQN folder on user {} ({})".format(username, userID))
					userHelper.setAqn(userID)

			# Console output
			consoleHelper.printColored("----", bcolors.PINK)
			fileNameShort = fileName[:32]+"..." if len(fileName) > 32 else fileName[:-4]
			consoleHelper.printGetScoresMessage("Requested beatmap {} ({})".format(fileNameShort, md5))

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
			self.write("error: ban")
		except exceptions.loginFailedException:
			self.write("error: pass")
		except:
			msg = "Unknown error in get scores!\n```{}\n{}```".format(sys.exc_info(), traceback.format_exc())
			consoleHelper.printColored("[!] {}".format(msg), bcolors.RED)
			discordBotHelper.sendConfidential(msg, True)
		finally:
			self.finish()
