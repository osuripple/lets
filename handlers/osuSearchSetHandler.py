import tornado.gen
import tornado.web

from common.web import requestsManager
from constants import exceptions
from common.sentry import sentry
from helpers import levbodHelper

MODULE_NAME = "direct_np"
class handler(requestsManager.asyncRequestHandler):
	"""
	Handler for /web/osu-search-set.php
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	@sentry.captureTornado
	def asyncGet(self):
		output = ""
		try:
			# Get data by beatmap id or beatmapset id
			if "b" in self.request.arguments:
				data = levbodHelper.getBeatmap(self.get_argument("b"))
			elif "s" in self.request.arguments:
				data = levbodHelper.getBeatmap(self.get_argument("s"))
			else:
				raise exceptions.invalidArgumentsException(MODULE_NAME)

			# Make sure levbod returned some valid data
			if data is None or len(data) == 0:
				raise exceptions.osuApiFailException(MODULE_NAME)

			# Write the response
			output = levbodHelper.levbodToDirectNp(data)+"\r\n"
		except (exceptions.invalidArgumentsException, exceptions.osuApiFailException):
			output = ""
		finally:
			self.write(output)