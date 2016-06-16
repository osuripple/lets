import json
from helpers import requestHelper

class handler(requestHelper.asyncRequestHandler):
	"""
	Handler for /api/v1/status
	"""
	def asyncGet(self):
		self.write(json.dumps({"status": 200, "server_status": 1}))
		#self.finish()
