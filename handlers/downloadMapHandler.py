import sys
import traceback

import tornado.gen
import tornado.web
from raven.contrib.tornado import SentryMixin

from common.web import requestsManager
from common.log import logUtils as log
from objects import glob

MODULE_NAME = "direct_download"
class handler(SentryMixin, requestsManager.asyncRequestHandler):
	"""
	Handler for /d/
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self, bid):
		try:
			self.set_status(302, "Moved Temporarily")
			url = "http://bm6.ppy.sh/{}.osz".format(bid)
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
