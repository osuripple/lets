import tornado.web
import json

class handler(tornado.web.RequestHandler):
	"""
	Handler for /api/v1/status
	"""
	def get(self):
		self.write(json.dumps({"status": 200, "server_status": 1}))
