from helpers import osuapiHelper
from constants import exceptions
from helpers import consoleHelper
from helpers import requestHelper

MODULE_NAME = "maps"
class handler(requestHelper.asyncRequestHandler):
	def asyncGet(self, fileName = None):
		try:
			# Check arguments
			if fileName == None:
				raise exceptions.invalidArgumentsException(MODULE_NAME)
			if fileName == "":
				raise exceptions.invalidArgumentsException(MODULE_NAME)

			fileNameShort = fileName[:32]+"..." if len(fileName) > 32 else fileName[:-4]
			consoleHelper.printMapsMessage("Requested .osu file {}".format(fileNameShort))

			# Get .osu file from osu! server
			fileContent = osuapiHelper.getOsuFileFromName(fileName)
			if fileContent == None:
				raise exceptions.osuApiFailException(MODULE_NAME)
			self.write(str(fileContent))
		except exceptions.invalidArgumentsException:
			self.send_error()
		except exceptions.osuApiFailException:
			self.send_error()
		finally:
			self.finish()
