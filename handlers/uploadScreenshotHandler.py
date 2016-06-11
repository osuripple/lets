import glob
from constants import exceptions
from helpers import generalHelper
from helpers import requestHelper
import os
from helpers import logHelper as log
from helpers.exceptionsTracker import trackExceptions

MODULE_NAME = "screenshot"
class handler(requestHelper.asyncRequestHandler):
	"""
	Handler for /web/osu-screenshot.php
	"""
	@trackExceptions(MODULE_NAME)
	def asyncPost(self):
		try:
			# Make sure screenshot file was passed
			if "ss" not in self.request.files:
				raise exceptions.invalidArgumentsException(MODULE_NAME)

			# Get a random screenshot id
			found = False
			while found == False:
				screenshotID = generalHelper.randomString(8)
				if os.path.isfile(".data/screenshots/{}.jpg".format(screenshotID)) == False:
					found = True

			# Write screenshot file to .data folder
			with open(".data/screenshots/{}.jpg".format(screenshotID), "wb") as f:
				f.write(self.request.files["ss"][0]["body"])

			# Output
			log.info("New screenshot ({})".format(screenshotID))

			# Return screenshot link
			self.write("{}/ss/{}.jpg".format(glob.conf.config["server"]["serverurl"], screenshotID))
		except exceptions.invalidArgumentsException:
			pass
		finally:
			self.finish()
