import tornado.gen
import tornado.web
import logging

from common.web import requestsManager
from common.sentry import sentry


class handler(requestsManager.asyncRequestHandler):
	"""
	Handler for /d/
	"""
	MODULE_NAME = "direct_download"

	@tornado.web.asynchronous
	@tornado.gen.engine
	@sentry.captureTornado
	def asyncGet(self, bid):
		try:
			noVideo = bid.endswith("n")
			if noVideo:
				bid = bid[:-1]
			bid = int(bid)

			self.set_status(302, "Moved Temporarily")
			domain = "bm6.ppy.sh" if self.request.host.lower() == "osu.ppy.sh" else "storage.ripple.moe"
			url = "https://{}/d/{}{}".format(domain, bid, "?novideo" if noVideo else "")
			self.add_header("Location", url)
			self.add_header("Cache-Control", "no-cache")
			self.add_header("Pragma", "no-cache")
		except ValueError:
			self.set_status(400)
			self.write("Invalid set id")
