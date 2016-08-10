from helpers import requestHelper
from helpers import logHelper as log
import tornado.web
import tornado.gen
import requests

class handler(requestHelper.asyncRequestHandler):
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self):
		try:
            if requestHelper.checkArguments(self.request.arguments, ["stream", "action"]) == False:
                self.write("missing params")
                return

			response = requests.get("https://osu.ppy.sh/web/check-updates.php?stream={}&action={}".format(self.get_argument("stream"), self.get_argument("action")))
			self.write(response.text)
		except Exception as e:
			log.error("check-updates failed: {}".format(e))
			self.write("")
