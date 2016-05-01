import tornado.web
from constants import exceptions
from helpers import generalHelper
from helpers import consoleHelper
import os

MODULE_NAME = "screenshot"
class handler(tornado.web.RequestHandler):
	"""
	Handler for /ss/
	"""
	def get(self, screenshotID = None):
		try:
			# Make sure the screenshot exists
			if screenshotID == None or os.path.isfile(".data/screenshots/{}".format(screenshotID)) == False:
				raise exceptions.fileNotFoundException(MODULE_NAME, screenshotID)

			# Read screenshot
			with open(".data/screenshots/{}".format(screenshotID), "rb") as f:
				data = f.read()

			# Output
			consoleHelper.printScreenshotsMessage("Served screenshot {}".format(screenshotID))

			# Display screenshot
			self.set_header("Content-type", "image/jpg")
			self.set_header("Content-length", len(data))
			self.write(data)
		except exceptions.fileNotFoundException:
			self.send_error(404)
