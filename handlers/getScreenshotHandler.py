from constants import exceptions
from helpers import requestHelper
from helpers import logHelper as log
import os
from helpers.exceptionsTracker import trackExceptions
import glob

# Exception tracking
import tornado.web
import tornado.gen
import sys
import traceback
from raven.contrib.tornado import SentryMixin

MODULE_NAME = "get_screenshot"
class handler(SentryMixin, requestHelper.asyncRequestHandler):
	"""
	Handler for /ss/
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self, screenshotID = None):
		try:
			# Make sure the screenshot exists
			if screenshotID == None or os.path.isfile(".data/screenshots/{}".format(screenshotID)) == False:
				raise exceptions.fileNotFoundException(MODULE_NAME, screenshotID)

			# Read screenshot
			with open(".data/screenshots/{}".format(screenshotID), "rb") as f:
				data = f.read()

			# Output
			log.info("Served screenshot {}".format(screenshotID))

			# Display screenshot
			self.set_header("Content-type", "image/jpg")
			self.set_header("Content-length", len(data))
			self.write(data)
		except exceptions.fileNotFoundException:
			self.send_error(404)
		except:
			log.error("Unknown error in {}!\n```{}\n{}```".format(MODULE_NAME, sys.exc_info(), traceback.format_exc()))
			if glob.sentry:
				yield tornado.gen.Task(self.captureException, exc_info=True)
		#finally:
		#	self.finish()
