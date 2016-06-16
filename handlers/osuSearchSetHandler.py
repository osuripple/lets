from constants import exceptions
from helpers import requestHelper
from helpers import userHelper
from helpers import osuapiHelper
from helpers import logHelper as log
import glob

# Exception tracking
import tornado.web
import tornado.gen
from raven.contrib.tornado import SentryMixin

MODULE_NAME = "direct_np"
class handler(SentryMixin, requestHelper.asyncRequestHandler):
	"""
	Handler for /web/osu-search-set.php
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self):
		try:
			# Get request ip
			#ip = self.getRequestIP()

			# Check arguments
			#if requestHelper.checkArguments(self.request.arguments, ["u", "h", "b"]) == False:
			#	raise exceptions.invalidArgumentsException(MODULE_NAME)

			# Get arguments
			#username = self.get_argument("u")
			#password = self.get_argument("h")
			if "b" in self.request.arguments:
				query = self.get_argument("b")
				searchby = "b"
			elif "s" in self.request.arguments:
				query = self.get_argument("s")
				searchby = "s"
			else:
				raise exceptions.invalidArgumentsException

			# Login check
			#userID = userHelper.getID(username)
			#if userID == 0:
			#	raise exceptions.loginFailedException(MODULE_NAME, username)
			#userHelper.checkLogin(userID, password, ip)

			# Bloodcat URL
			bcURL = "http://bloodcat.com/osu/?mod=json&c={}&q={}".format(searchby, query)
			log.debug(bcURL)

			# Get data from bloodcat API
			bcData = osuapiHelper.bloodcatRequest(bcURL)
			if bcData == None:
				raise exceptions.osuApiFailException
			if len(bcData) == 0:
				raise exceptions.osuApiFailException

			# Output string
			log.debug(str(bcData[0]))
			output = osuapiHelper.bloodcatToDirect(bcData[0], True)+"\r\n"

			# Return response
			self.write(output)
		except exceptions.invalidArgumentsException:
			pass
		except exceptions.loginFailedException:
			pass
		except exceptions.osuApiFailException:
			pass
		except:
			log.error("Unknown error in {}!\n```{}\n{}```".format(MODULE_NAME, sys.exc_info(), traceback.format_exc()))
			if glob.sentry:
				yield tornado.gen.Task(self.captureException, exc_info=True)
		#finally:
		#	self.finish()
