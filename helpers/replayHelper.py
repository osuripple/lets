import io
import os

from botocore.exceptions import ClientError

from common import generalUtils
from constants import exceptions, dataTypes
from helpers import binaryHelper, s3
from objects import glob

def toDotTicks(unixTime):
	"""
	:param unixTime: Unix timestamp
	"""
	return (10000000*unixTime) + 621355968000000000


def getRawReplayDisk(scoreID):
	fileName = _getFirstReplayFileName(scoreID)
	if fileName is None:
		raise FileNotFoundError()
	with open(fileName, "rb") as f:
		return f.read()


def getRawReplayS3(scoreID):
	with io.BytesIO() as f:
		try:
			s3.getClient().download_fileobj(glob.conf["_S3_REPLAYS_BUCKET"], "replay_{}.osrxd".format(scoreID), f)
		except ClientError as e:
			if e.response["Error"]["Code"] == "404":
				raise FileNotFoundError()
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

def buildFullReplay(scoreID=None, scoreData=None, rawReplay=None, useS3=False):
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

	if rawReplay is None:
		rawReplay = (getRawReplayDisk if not useS3 else getRawReplayS3)(scoreID)

	# Calculate missing replay data
	rank = generalUtils.getRank(int(scoreData["play_mode"]), int(scoreData["mods"]), int(scoreData["accuracy"]),
								int(scoreData["300_count"]), int(scoreData["100_count"]), int(scoreData["50_count"]),
								int(scoreData["misses_count"]))
	magicHash = generalUtils.stringMd5(
		"{}p{}o{}o{}t{}a{}r{}e{}y{}o{}u{}{}{}".format(int(scoreData["100_count"]) + int(scoreData["300_count"]),
													  scoreData["50_count"], scoreData["gekis_count"],
													  scoreData["katus_count"], scoreData["misses_count"],
													  scoreData["beatmap_md5"], scoreData["max_combo"],
													  "True" if int(scoreData["full_combo"]) == 1 else "False",
													  scoreData["username"], scoreData["score"], rank,
													  scoreData["mods"], "True"))
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