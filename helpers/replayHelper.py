import io
import os

from botocore.exceptions import ClientError
from timeout_decorator import timeout

from common import generalUtils
from common.log import logUtils as log
from common.sentry import sentry
from constants import exceptions
from constants import dataTypes
from helpers import binaryHelper
from helpers import s3
from objects import glob


def toDotTicks(unixTime):
	"""
	:param unixTime: Unix timestamp
	"""
	return (10000000*unixTime) + 621355968000000000


def _getRawReplayFailedLocal(scoreID):
	with open(os.path.join(glob.conf["FAILED_REPLAYS_FOLDER"], "replay_{}.osr".format(scoreID)), "rb") as f:
		return f.read()


@timeout(5, use_signals=False)
def getRawReplayS3(scoreID):
	scoreID = int(scoreID)
	if not glob.conf.s3_enabled:
		log.warning("S3 is disabled! Using failed local")
		return _getRawReplayFailedLocal(scoreID)

	fileName = "replay_{}.osr".format(scoreID)
	log.debug("Downloading {} from s3".format(fileName))
	with io.BytesIO() as f:
		bucket = s3.getReadReplayBucketName(scoreID)
		try:
			glob.threadScope.s3.download_fileobj(bucket, fileName, f)
		except ClientError as e:
			# 404 -> no such key
			# 400 -> no such bucket
			code = e.response["Error"]["Code"]
			if code in ("404", "400"):
				log.warning("S3 replay returned {}, trying to get from failed replays".format(code))
				if code == "400":
					sentry.captureMessage("Invalid S3 replays bucket ({})! (got error 400)".format(bucket))
				return _getRawReplayFailedLocal(scoreID)
			raise
		f.seek(0)
		return f.read()


def _getFirstReplayFileName(scoreID):
	"""
	Iterates over all REPLAYS_FOLDERS in config, and returns the
	path of the replay. It starts from the first folder, if the replay
	is not there, it tries with the second folder and so on.
	Returns None if there's no such file in any of the folders.

	:param scoreID:
	:return: path or None
	"""
	for folder in glob.conf["REPLAYS_FOLDERS"]:
		fileName = "{}/replay_{}.osr".format(folder, scoreID)
		if os.path.isfile(fileName):
			return fileName
	return None


def buildFullReplay(scoreID=None, scoreData=None, rawReplay=None):
	if all(v is None for v in (scoreID, scoreData)) or all(v is not None for v in (scoreID, scoreData)):
		raise AttributeError("Either scoreID or scoreData must be provided, not neither or both")

	if scoreData is None:
		scoreData = glob.db.fetch(
			"SELECT scores.*, users.username FROM scores LEFT JOIN users ON scores.userid = users.id "
			"WHERE scores.id = %s",
			[scoreID]
		)
	else:
		scoreID = scoreData["id"]
	if scoreData is None or scoreID is None:
		raise exceptions.scoreNotFoundError()
	scoreID = int(scoreID)

	if rawReplay is None:
		rawReplay = getRawReplayS3(scoreID)

	# Calculate missing replay data
	rank = generalUtils.getRank(
		int(scoreData["play_mode"]),
		int(scoreData["mods"]),
		int(scoreData["accuracy"]),
		int(scoreData["300_count"]),
		int(scoreData["100_count"]),
		int(scoreData["50_count"]),
		int(scoreData["misses_count"])
	)
	magicHash = generalUtils.stringMd5(
		"{}p{}o{}o{}t{}a{}r{}e{}y{}o{}u{}{}{}".format(
			int(scoreData["100_count"]) + int(scoreData["300_count"]),
			scoreData["50_count"],
			scoreData["gekis_count"],
			scoreData["katus_count"],
			scoreData["misses_count"],
			scoreData["beatmap_md5"],
			scoreData["max_combo"],
			"True" if int(scoreData["full_combo"]) == 1 else "False",
			scoreData["username"],
			scoreData["score"],
			rank,
			scoreData["mods"],
			"True"
		)
	)
	# Add headers (convert to full replay)
	fullReplay = binaryHelper.binaryWrite([
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
		[toDotTicks(int(scoreData["time"])), dataTypes.uInt64],
		[rawReplay, dataTypes.rawReplay],
		[0, dataTypes.uInt32],
		[0, dataTypes.uInt32],
	])

	# Return full replay
	return fullReplay