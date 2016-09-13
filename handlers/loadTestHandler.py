import glob

from helpers import requestHelper
import tornado.web
import tornado.gen

class handler(requestHelper.asyncRequestHandler):
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self):
		if not glob.debug:
			self.write("Nope")
			return
		glob.db.fetchAll("SELECT * FROM beatmaps")
		glob.db.fetchAll("SELECT * FROM users")
		glob.db.fetchAll("SELECT * FROM scores")
		self.write("ibmd")
