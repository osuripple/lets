from helpers import userHelper
import glob
from constants import exceptions
from helpers import requestHelper
from helpers import logHelper as log
from helpers.exceptionsTracker import trackExceptions

MODULE_NAME = "bancho_connect"
class handler(requestHelper.asyncRequestHandler):
	"""
	Handler for /web/bancho_connect.php
	"""
	@trackExceptions(MODULE_NAME)
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
			if userHelper.getAllowed(userID) == 0:
				raise exceptions.userBannedException(MODULE_NAME, username)

			# Update latest activity
			userHelper.updateLatestActivity(userID)

			# Get country and output it
			country = glob.db.fetch("SELECT country FROM users_stats WHERE id = %s", [userID])["country"]
			self.write(country)
		except exceptions.invalidArgumentsException:
			pass
		except exceptions.loginFailedException:
			self.write("error: pass")
		except exceptions.userBannedException:
			pass
		finally:
			self.finish()
