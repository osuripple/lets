import tornado.web
from helpers import osuapiHelper
import glob
from constants import exceptions
from urllib.parse import unquote
from constants import bcolors
from helpers import consoleHelper

MODULE_NAME = "maps"
class handler(tornado.web.RequestHandler):
	def get(self, fileName = None):
		try:
			# Check arguments
			if fileName == None:
				raise exceptions.invalidArgumentsException(MODULE_NAME)
			if fileName == "":
				raise exceptions.invalidArgumentsException(MODULE_NAME)

			# Get beatmap id from file name
			fileName = unquote(fileName)[:-4]
			print(fileName)
			beatmapID = glob.db.fetch("SELECT beatmap_id FROM beatmaps WHERE song_name = ?", [fileName])
			if beatmapID == None:
				raise exceptions.noBeatmapException(MODULE_NAME, fileName)
			beatmapID = beatmapID["beatmap_id"]

			# Get .osu file
			fileContent = osuapiHelper.getOsuFile(beatmapID)
			consoleHelper.printColored(str(fileContent), bcolors.GREEN)
			self.write(str(fileContent))
		except exceptions.invalidArgumentsException:
			self.send_error()
			pass
		except exceptions.noBeatmapException:
			self.send_error()
			pass
