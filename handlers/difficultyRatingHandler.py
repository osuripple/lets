import requests
import tornado.gen
import tornado.web

from common.log import logUtils as log
from common.web import requestsManager

class handler(requestsManager.asyncRequestHandler):
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncPost(self):
		try:
			headers = {'Content-type': 'application/json'}
			data = self.request.body
			response = requests.post("https://osu.ppy.sh/difficulty-rating", data=data, headers=headers)
			self.write(response.text)
		except Exception as e:
			log.error("difficulty-rating failed: {}".format(e))
			self.write("")
