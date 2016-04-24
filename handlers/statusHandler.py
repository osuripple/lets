import tornado.web
import json

class handler(tornado.web.RequestHandler):
	"""
	Handler for /status
	"""
	def get(self):
		self.write(json.dumps({"response": 200, "status": 1}))
