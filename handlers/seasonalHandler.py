import requests
import tornado.web

from common.web import requestsManager


class handler(requestsManager.asyncRequestHandler):
	MODULE_NAME = "seasonal"

	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self):
		self.write(requests.get("http://s.ripple.moe/bg.json", timeout=5).text)
