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
			args = "?"
			for i in self.request.arguments:
				args += "&"+i+"="+self.get_argument(i)
			#if requestHelper.checkArguments(self.request.arguments, ["stream", "action"]) == False:
			#	self.write("missing params")
			#	return

			url = "https://osu.ppy.sh/web/check-updates.php{}".format(args)
			print(str(url))
			response = requests.get(url)
			print(str(response.text))
			self.write(response.text)
		except Exception as e:
			log.error("check-updates failed: {}".format(e))
			self.write("")
