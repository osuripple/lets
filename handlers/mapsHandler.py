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

			fileNameShort = fileName[:32]+"..." if len(fileName) > 32 else fileName[:-4]
			consoleHelper.printMapsMessage("Requested .osu file {}".format(fileNameShort))

			# Get .osu file from osu! server
			fileContent = osuapiHelper.getOsuFile(fileName)
			if fileContent == None:
				raise exceptions.osuApiFailException(MODULE_NAME)
			self.write(str(fileContent))
		except exceptions.invalidArgumentsException:
			self.send_error()
		except exceptions.osuApiFailException:
			self.send_error()
