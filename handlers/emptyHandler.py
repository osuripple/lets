import tornado.gen
import tornado.web

from common.web import requestsManager


class handler(requestsManager.asyncRequestHandler):
	MODULE_NAME = "empty"

	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self):
		self.write("Not yet")
