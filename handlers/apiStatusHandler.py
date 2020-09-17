import json

from common.web import requestsManager


class handler(requestsManager.asyncRequestHandler):
	"""
	Handler for /api/v1/status
	"""
	MODULE_NAME = "api/status"

	def asyncGet(self):
		self.write(json.dumps({"status": 200, "server_status": 1}))
