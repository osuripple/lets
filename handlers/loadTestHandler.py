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
		glob.db.fetchAll("SELECT SQL_NO_CACHE * FROM beatmaps")
		glob.db.fetchAll("SELECT SQL_NO_CACHE * FROM users")
		glob.db.fetchAll("SELECT SQL_NO_CACHE * FROM scores")
		self.write("ibmd")
