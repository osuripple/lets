import tornado.gen
import tornado.web
import timeout_decorator

import common.log.logUtils as log
from common.web import requestsManager
from constants import exceptions
from helpers import replayHelper
from common.sentry import sentry
from objects import glob


class handler(requestsManager.asyncRequestHandler):
	"""
	Handler for /replay/
	"""
	MODULE_NAME = "get_full_replay"

	@tornado.web.asynchronous
	@tornado.gen.engine
	@sentry.captureTornado
	def asyncGet(self, replayID):
		try:
			replayID = int(replayID)
			fullReplay = replayHelper.buildFullReplay(scoreID=replayID)
			self.write(fullReplay)
			self.add_header("Content-type", "application/octet-stream")
			self.set_header("Content-length", len(fullReplay))
			self.set_header("Content-Description", "File Transfer")
			self.set_header("Content-Disposition", "attachment; filename=\"{}.osr\"".format(replayID))
		except (exceptions.fileNotFoundException, exceptions.scoreNotFoundError, ValueError):
			self.set_status(404)
			self.write("Replay not found")
		except timeout_decorator.TimeoutError:
			log.error("S3 timed out")
			sentry.captureMessage("S3 timeout while fetching replay.")
			self.set_status(500)
			self.write("S3 Error")
			glob.stats["replay_download_failures"].labels(type="full_s3_timeout").inc()
		except:
			glob.stats["replay_download_failures"].labels(type="full_other").inc()
			self.set_status(500)
			self.write("Internal Server Error")
			raise
