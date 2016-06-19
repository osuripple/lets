from helpers import requestHelper
import requests
import glob

# Exception tracking
import tornado.web
import tornado.gen
import sys
import traceback
from raven.contrib.tornado import SentryMixin

MODULE_NAME = "direct_download"
class handler(SentryMixin, requestHelper.asyncRequestHandler):
	"""
	Handler for /d/
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self, bid):
		try:
			self.set_status(302, "Moved Temporarily")
			url = "http://m.zxq.co/direct/direct.php?id={}".format(bid)
			self.add_header("Location", url)
			self.add_header("Cache-Control", "no-cache")
			self.add_header("Pragma", "no-cache")
			print(url)
			#f = requests.get(url)
			#self.write(str(f))
		except:
			log.error("Unknown error in {}!\n```{}\n{}```".format(MODULE_NAME, sys.exc_info(), traceback.format_exc()))
			if glob.sentry:
				yield tornado.gen.Task(self.captureException, exc_info=True)
		#finally:
		#	self.finish()
