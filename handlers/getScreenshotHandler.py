import os
import sys
import traceback

import tornado.gen
import tornado.web
from raven.contrib.tornado import SentryMixin

from common.log import logUtils as log
from common.web import requestsManager
from constants import exceptions
from objects import glob
from common.sentry import sentry

class handler(requestsManager.asyncRequestHandler):
	"""
	Handler for /ss/
	"""
	MODULE_NAME = "get_screenshot"

	@tornado.web.asynchronous
	@tornado.gen.engine
	@sentry.captureTornado
	def asyncGet(self, screenshotID = None):
		try:
			# Make sure the screenshot exists
			if screenshotID is None or not os.path.isfile("{}/{}".format(glob.conf["SCREENSHOTS_FOLDER"], screenshotID)):
				raise exceptions.fileNotFoundException(self.MODULE_NAME, screenshotID)

			# Read screenshot
			with open("{}/{}".format(glob.conf["SCREENSHOTS_FOLDER"], screenshotID), "rb") as f:
				data = f.read()

			# Output
			log.info("Served screenshot {}".format(screenshotID))

			# Display screenshot
			self.write(data)
			self.set_header("Content-type", "image/jpg")
			self.set_header("Content-length", len(data))
		except exceptions.fileNotFoundException:
			self.set_status(404)
