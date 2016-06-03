from helpers import requestHelper
import requests

MODULE_NAME = "direct_download"
class handler(requestHelper.asyncRequestHandler):
	"""
	Handler for /d/
	"""
	def asyncGet(self, bid):
		try:
			self.set_status(302)
			url = "http://m.zxq.co/vinococco.php?id={}".format(bid)
			self.add_header("location", url)
			print(url)
			#f = requests.get(url)
			#self.write(str(f))
		finally:
			self.finish()
