from tornado.gen import engine
from tornado.web import asynchronous
from common.web import requestsManager

class handler(requestsManager.asyncRequestHandler):
	@asynchronous
	@engine
	def asyncPost(self):
		try:
			self.set_status(307, "Moved Temporarily")
			self.add_header("Location", f"https://osu.ppy.sh/difficulty-rating")
		except ValueError:
			self.set_status(400)
			self.write("")
