import os
import sys
import traceback

import tornado.gen
import tornado.web
from raven.contrib.tornado import SentryMixin

from common.log import logUtils as log
from common.web import requestsManager
from constants import dataTypes
from constants import exceptions
from helpers import binaryHelper
from common import generalUtils
from objects import glob
from common.sentry import sentry

MODULE_NAME = "get_full_replay"
class handler(requestsManager.asyncRequestHandler):
	"""
	Handler for /replay/
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	@sentry.captureTornado
	def asyncGet(self, replayID):
		try:
			# Make sure the score exists
			scoreData = glob.db.fetch("SELECT scores.*, users.username FROM scores LEFT JOIN users ON scores.userid = users.id WHERE scores.id = %s", [replayID])
			if scoreData is None:
				raise exceptions.fileNotFoundException(MODULE_NAME, replayID)

			# Make sure raw replay exists
			fileName = ".data/replays/replay_{}.osr".format(replayID)
			if not os.path.isfile(fileName):
				raise exceptions.fileNotFoundException(MODULE_NAME, fileName)

			# Read raw replay
			with open(fileName, "rb") as f:
				rawReplay = f.read()

			# Calculate missing replay data
			rank = generalUtils.getRank(int(scoreData["play_mode"]), int(scoreData["mods"]), int(scoreData["accuracy"]), int(scoreData["300_count"]), int(scoreData["100_count"]), int(scoreData["50_count"]), int(scoreData["misses_count"]))
			magicHash = generalUtils.stringMd5("{}p{}o{}o{}t{}a{}r{}e{}y{}o{}u{}{}{}".format(int(scoreData["100_count"]) + int(scoreData["300_count"]), scoreData["50_count"], scoreData["gekis_count"], scoreData["katus_count"], scoreData["misses_count"], scoreData["beatmap_md5"], scoreData["max_combo"], "True" if int(scoreData["full_combo"]) == 1 else "False", scoreData["username"], scoreData["score"], rank, scoreData["mods"], "True"))
			# Add headers (convert to full replay)
			fullReplay =  binaryHelper.binaryWrite([
				[scoreData["play_mode"], dataTypes.byte],
				[20150414, dataTypes.uInt32],
				[scoreData["beatmap_md5"], dataTypes.string],
				[scoreData["username"], dataTypes.string],
				[magicHash, dataTypes.string],
				[scoreData["300_count"], dataTypes.uInt16],
				[scoreData["100_count"], dataTypes.uInt16],
				[scoreData["50_count"], dataTypes.uInt16],
				[scoreData["gekis_count"], dataTypes.uInt16],
				[scoreData["katus_count"], dataTypes.uInt16],
				[scoreData["misses_count"], dataTypes.uInt16],
				[scoreData["score"], dataTypes.uInt32],
				[scoreData["max_combo"], dataTypes.uInt16],
				[scoreData["full_combo"], dataTypes.byte],
				[scoreData["mods"], dataTypes.uInt32],
				[0, dataTypes.byte],
				[0, dataTypes.uInt64],
				[rawReplay, dataTypes.rawReplay],
				[0, dataTypes.uInt32],
				[0, dataTypes.uInt32],
			])

			# Serve full replay
			self.write(fullReplay)
			self.add_header("Content-type", "application/octet-stream")
			self.set_header("Content-length", len(fullReplay))
			self.set_header("Content-Description", "File Transfer")
			self.set_header ("Content-Disposition", "attachment; filename=\"{}.osr\"".format(scoreData["id"]))
		except exceptions.fileNotFoundException:
			self.write("Replay not found")