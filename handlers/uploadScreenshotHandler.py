import os
import io
import sys
import traceback

import tornado.gen
import tornado.web
from raven.contrib.tornado import SentryMixin
import botocore.errorfactory

from common.log import logUtils as log
from common.ripple import userUtils
from common.web import requestsManager
from constants import exceptions
from common import generalUtils
from objects import glob
from common.sentry import sentry

MODULE_NAME = "screenshot"
class handler(requestsManager.asyncRequestHandler):
	"""
	Handler for /web/osu-screenshot.php
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	@sentry.captureTornado
	def asyncPost(self):
		try:
			if glob.conf["DEBUG"]:
				requestsManager.printArguments(self)

			# Make sure screenshot file was passed
			if "ss" not in self.request.files:
				raise exceptions.invalidArgumentsException(MODULE_NAME)

			# Check user auth because of sneaky people
			if not requestsManager.checkArguments(self.request.arguments, ["u", "p"]):
				raise exceptions.invalidArgumentsException(MODULE_NAME)
			username = self.get_argument("u")
			password = self.get_argument("p")
			ip = self.getRequestIP()
			userID = userUtils.getID(username)
			if not userUtils.checkLogin(userID, password):
				raise exceptions.loginFailedException(MODULE_NAME, username)
			if userUtils.check2FA(userID, ip):
				raise exceptions.need2FAException(MODULE_NAME, username, ip)

			# Rate limit
			if glob.redis.get("lets:screenshot:{}".format(userID)) is not None:
				self.write("no")
				return
			glob.redis.set("lets:screenshot:{}".format(userID), 1, 60)

			# Get a random screenshot id
			hasS3 = bool(glob.conf["S3_SCREENSHOTS_BUCKET"]) \
				and bool(glob.conf["S3_SCREENSHOTS_REGION"]) \
				and bool(glob.conf["S3_SCREENSHOTS_ENDPOINT_URL"])
			found = False
			screenshotID = ""
			while not found:
				screenshotID = generalUtils.randomString(8)
				if hasS3:
					try:
						glob.threadScope.s3Screenshots.head_object(
							Bucket=glob.conf["S3_SCREENSHOTS_BUCKET"],
							Key=f"{screenshotID}.jpg"
						)
						found = False
					except botocore.errorfactory.ClientError:
						found = True
				else:
					found = not os.path.isfile("{}/{}.jpg".format(glob.conf["SCREENSHOTS_FOLDER"], screenshotID))

			# Output
			log.info("New screenshot ({})".format(screenshotID))

			# Write screenshot file to .data folder
			if hasS3:
				with io.BytesIO(self.request.files["ss"][0]["body"]) as f:
					glob.threadScope.s3Screenshots.upload_fileobj(
						f,
						glob.conf["S3_SCREENSHOTS_BUCKET"],
						f"{screenshotID}.jpg",
						ExtraArgs={"ACL": "public-read"}
					)
			else:
				with open("{}/{}.jpg".format(glob.conf["SCREENSHOTS_FOLDER"], screenshotID), "wb") as f:
					f.write(self.request.files["ss"][0]["body"])

			# Return screenshot link
			self.write("{}/ss/{}.jpg".format(glob.conf["SERVER_URL"], screenshotID))
		except exceptions.need2FAException:
			pass
		except exceptions.invalidArgumentsException:
			pass
		except exceptions.loginFailedException:
			pass