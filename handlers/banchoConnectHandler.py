from helpers import userHelper
import glob
from constants import exceptions
from helpers import requestHelper
from helpers import logHelper as log
from helpers.exceptionsTracker import trackExceptions

# Exception tracking
import tornado.web
import tornado.gen
import sys
import traceback
from raven.contrib.tornado import SentryMixin

MODULE_NAME = "bancho_connect"
class handler(SentryMixin, requestHelper.asyncRequestHandler):
	"""
	Handler for /web/bancho_connect.php
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self):
		try:
			# Get request ip
			ip = self.getRequestIP()

			# Argument check
			if requestHelper.checkArguments(self.request.arguments, ["u", "h"]) == False:
				raise exceptions.invalidArgumentsException(MODULE_NAME)

			# Get user ID
			username = self.get_argument("u")
			userID = userHelper.getID(username)
			if userID == None:
				raise exceptions.loginFailedException(MODULE_NAME, username)

			# Check login
			log.info("{} ({}) wants to connect".format(username, userID))
			if userHelper.checkLogin(userID, self.get_argument("h"), ip) == False:
				raise exceptions.loginFailedException(MODULE_NAME, username)

			# Ban check
			if userHelper.isBanned(userID) == True:
				raise exceptions.userBannedException(MODULE_NAME, username)

			# 2FA check
			if userHelper.check2FA(userID, ip):
				raise exceptions.need2FAException(MODULE_NAME, username, ip)

			# Update latest activity
			userHelper.updateLatestActivity(userID)

			# Get country and output it
			country = glob.db.fetch("SELECT country FROM users_stats WHERE id = %s", [userID])["country"]
			self.write(country)
		except exceptions.invalidArgumentsException:
			pass
		except exceptions.loginFailedException:
			self.write("error: pass\n")
		except exceptions.userBannedException:
			pass
		except exceptions.need2FAException:
			self.write("error: verify\n")
		except:
			log.error("Unknown error in {}!\n```{}\n{}```".format(MODULE_NAME, sys.exc_info(), traceback.format_exc()))
			if glob.sentry:
				yield tornado.gen.Task(self.captureException, exc_info=True)
		#finally:
		#	self.finish()
