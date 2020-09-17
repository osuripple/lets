import tornado.gen
import tornado.web

from common.sentry import sentry
from common.web import requestsManager
from common.web import cheesegull
from common.log import logUtils as log
from constants import exceptions

class handler(requestsManager.asyncRequestHandler):
	"""
	Handler for /web/osu-search-set.php
	"""
	MODULE_NAME = "osu_direct_np"

	@tornado.web.asynchronous
	@tornado.gen.engine
	@sentry.captureTornado
	def asyncGet(self):
		output = ""
		try:
			# Get data by beatmap id or beatmapset id
			if "b" in self.request.arguments:
				_id = self.get_argument("b")
				data = cheesegull.getBeatmap(_id)
			elif "s" in self.request.arguments:
				_id = self.get_argument("s")
				data = cheesegull.getBeatmapSet(_id)
			else:
				raise exceptions.invalidArgumentsException(self.MODULE_NAME)

			log.info("Requested osu!direct np: {}/{}".format("b" if "b" in self.request.arguments else "s", _id))

			# Make sure cheesegull returned some valid data
			if data is None or len(data) == 0:
				raise exceptions.osuApiFailException(self.MODULE_NAME)

			# Write the response
			output = cheesegull.toDirectNp(data) + "\r\n"
		except (exceptions.invalidArgumentsException, exceptions.osuApiFailException, KeyError):
			output = ""
		finally:
			self.write(output)