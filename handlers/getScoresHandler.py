import beatmap
import scoreboard
import tornado.web
import glob
from helpers import consoleHelper
from constants import bcolors
from constants import exceptions
from helpers import requestHelper

MODULE_NAME = "get_scores"
class handler(tornado.web.RequestHandler):
	"""
	Handler for /web/osu-osz2-getscores.php
	"""
	def get(self):
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
			consoleHelper.printColored("----", bcolors.PINK)
			fileNameShort = fileName[:32]+"..." if len(fileName) > 32 else fileName[:-4]
			consoleHelper.printGetScoresMessage("Requested beatmap {} ({})".format(fileNameShort, md5))

			# TODO: Login check

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
			pass
		except exceptions.loginFailedException:
			pass
