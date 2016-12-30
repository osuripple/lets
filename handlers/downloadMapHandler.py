import tornado.gen
import tornado.web

from common.web import requestsManager
from common.sentry import sentry

MODULE_NAME = "direct_download"
class handler(requestsManager.asyncRequestHandler):
	"""
	Handler for /d/
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	@sentry.captureTornado
	def asyncGet(self, bid):
		self.set_status(302, "Moved Temporarily")
		url = "http://bm6.ppy.sh/{}.osz".format(bid)
		self.add_header("Location", url)
		self.add_header("Cache-Control", "no-cache")
		self.add_header("Pragma", "no-cache")