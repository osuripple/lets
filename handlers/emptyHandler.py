from helpers import requestHelper
import tornado.web
import tornado.gen

class handler(requestHelper.asyncRequestHandler):
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self):
		print("404 (empty handler): {}".format(self.request.uri))
		self.set_status(404)
		self.write("Not yet")
