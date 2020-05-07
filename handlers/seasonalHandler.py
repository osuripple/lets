import requests
import tornado.web

from common.web import requestsManager


class handler(requestsManager.asyncRequestHandler):
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self):
		self.write(requests.get("https://osu.ppy.sh/web/osu-getseasonal.php", timeout=5).text)
