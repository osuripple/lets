from helpers import requestHelper
import tornado.web
import tornado.gen

class handler(requestHelper.asyncRequestHandler):
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self):
		self.write("")
