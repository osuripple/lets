from helpers import requestHelper
import logHelper as log
import tornado.web
import tornado.gen
import requests

class handler(requestHelper.asyncRequestHandler):
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self):
		try:
			response = requests.get("https://osu.ppy.sh/web/check-updates.php")
			self.write(response.text)
		except Exception as e:
			log.error("check-updates failed: {}".format(e))
			self.write("")
