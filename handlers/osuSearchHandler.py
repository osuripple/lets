import tornado.gen
import tornado.web

from common.web import requestsManager
from constants import exceptions
from helpers import osuapiHelper
from common.sentry import sentry

MODULE_NAME = "direct"
class handler(requestsManager.asyncRequestHandler):
	"""
	Handler for /web/osu-search.php
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	@sentry.captureTornado
	def asyncGet(self):
		output = ""
		try:
			gameMode = self.get_argument("m", "-1")
			rankedStatus = self.get_argument("r", "-1")
			query = self.get_argument("q", "")
			page = int(self.get_argument("p", "0"))
			if query.lower() in ["newest", "top rated", "most played"]:
				query = ""

			# Get data from levbod API
			levbodData = osuapiHelper.levbodRequest(True, rankedStatus=rankedStatus, page=page, gameMode=gameMode, query=query)
			if levbodData is None:
				raise exceptions.noAPIDataError()

			# Write output
			output += "999" if len(levbodData) == 100 else str(len(levbodData))
			output += "\n"
			for beatmapSet in levbodData:
				output += osuapiHelper.levbodToDirect(beatmapSet)+"\r\n"
		except exceptions.noAPIDataError:
			output = "0\n"
		finally:
			self.write(output)
