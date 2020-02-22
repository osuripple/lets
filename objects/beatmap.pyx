import time

from common.constants import gameModes
from common.log import logUtils as log
from constants import rankedStatuses
from helpers import osuapiHelper
import objects.glob
from helpers.generalHelper import clamp


class beatmap:
	__slots__ = ("songName", "fileMD5", "rankedStatus", "rankedStatusFrozen", "beatmapID", "beatmapSetID", "offset",
	             "rating", "starsStd", "starsTaiko", "starsCtb", "starsMania", "AR", "OD", "maxCombo", "hitLength",
	             "bpm", "playcount" ,"passcount", "refresh", "disablePP", "fileName")

	def __init__(self, md5 = None, beatmapSetID = None, gameMode = 0, refresh=False, fileName=None):
		"""
		Initialize a beatmap object.

		md5 -- beatmap md5. Optional.
		beatmapSetID -- beatmapSetID. Optional.
		"""
		self.songName = ""
		self.fileMD5 = ""
		self.fileName = fileName
		self.rankedStatus = rankedStatuses.NOT_SUBMITTED
		self.rankedStatusFrozen = 0
		self.beatmapID = 0
		self.beatmapSetID = 0
		self.offset = 0		# Won't implement
		self.rating = 0.

		self.starsStd = 0.0		# stars for converted
		self.starsTaiko = 0.0	# stars for converted
		self.starsCtb = 0.0		# stars for converted
		self.starsMania = 0.0	# stars for converted
		self.AR = 0.0
		self.OD = 0.0
		self.maxCombo = 0
		self.hitLength = 0
		self.bpm = 0
		self.disablePP = False

		# Statistics for ranking panel
		self.playcount = 0

		# Force refresh from osu api
		self.refresh = refresh

		if md5 is not None and beatmapSetID is not None:
			self.setData(md5, beatmapSetID)

	def addBeatmapToDB(self):
		"""
		Add current beatmap data in db if not in yet
		"""
		# Make sure the beatmap is not already in db
		bdata = objects.glob.db.fetch(
			"SELECT id, ranked_status_freezed, ranked, disable_pp FROM beatmaps "
			"WHERE beatmap_md5 = %s OR beatmap_id = %s LIMIT 1",
			(self.fileMD5, self.beatmapID)
		)
		if bdata is not None:
			# This beatmap is already in db, remove old record
			# Get current frozen status
			frozen = bdata["ranked_status_freezed"]
			if frozen:
				self.rankedStatus = bdata["ranked"]
			self.disablePP = bdata["disable_pp"]
			log.debug("Deleting old beatmap data ({})".format(bdata["id"]))
			objects.glob.db.execute("DELETE FROM beatmaps WHERE id = %s LIMIT 1", [bdata["id"]])
		else:
			# Unfreeze beatmap status
			frozen = False

		# Unrank broken approved/qualified/loved maps
		if not self.disablePP and self.rankedStatus >= rankedStatuses.APPROVED:
			from objects.score import PerfectScoreFactory
			# Calculate PP for every game mode
			log.debug("Caching A/Q/L map ({}). Checking if it's broken.".format(self.fileMD5))
			for gameMode in (
				range(gameModes.STD, gameModes.MANIA) if not self.is_mode_specific
				else (self.specific_game_mode,)
			):
				log.debug("Calculating A/Q/L pp for beatmap {}, mode {}".format(self.fileMD5, gameMode))
				s = PerfectScoreFactory.create(self, game_mode=gameMode)
				s.calculatePP(self)
				if s.pp == 0:
					log.warning("Got 0.0pp while checking A/Q/L pp for beatmap {}".format(self.fileMD5))
					self.disablePP = True
					break

				if s.pp >= objects.glob.aqlThresholds[gameMode]:
					# More pp than the threshold
					self.disablePP = True
					break

		if self.disablePP:
			# dont()
			log.info("Disabling PP on broken A/Q/L map {}".format(self.fileMD5))
			self.disablePP = True
			objects.glob.db.execute("UPDATE scores SET pp = 0 WHERE beatmap_md5 = %s", (self.fileMD5,))

		# Add new beatmap data
		log.debug("Saving beatmap data in db...")
		params = [
			self.beatmapID,
			self.beatmapSetID,
			self.fileMD5,
			self.songName.encode("utf-8", "ignore").decode("utf-8"),
			self.AR,
			self.OD,
			self.starsStd,
			self.starsTaiko,
			self.starsCtb,
			self.starsMania,
			self.maxCombo,
			self.hitLength,
			clamp(self.bpm, -2147483648, 2147483647),
			self.rankedStatus if not frozen else 2,
			int(time.time()),
			frozen,
			self.disablePP
		]
		if self.fileName is not None:
			params.append(self.fileName)
		objects.glob.db.execute(
			"INSERT INTO `beatmaps` (`id`, `beatmap_id`, `beatmapset_id`, `beatmap_md5`, `song_name`, "
			"`ar`, `od`, `difficulty_std`, `difficulty_taiko`, `difficulty_ctb`, `difficulty_mania`, "
			"`max_combo`, `hit_length`, `bpm`, `ranked`, "
			"`latest_update`, `ranked_status_freezed`, `disable_pp`{extra_q}) "
			"VALUES (NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s{extra_p})".format(
				extra_q=", `file_name`" if self.fileName is not None else "",
				extra_p=", %s" if self.fileName is not None else "",
			), params
		)

	def saveFileName(self, fileName):
		# Temporary workaround to avoid re-fetching all beatmaps from osu!api
		r = objects.glob.db.fetch("SELECT file_name FROM beatmaps WHERE beatmap_md5 = %s LIMIT 1", (self.fileMD5,))
		if r is None:
			return
		if r["file_name"] is None:
			objects.glob.db.execute(
				"UPDATE beatmaps SET file_name = %s WHERE beatmap_md5 = %s LIMIT 1",
				(self.fileName, self.fileMD5)
			)

	def setDataFromDB(self, md5):
		"""
		Set this object's beatmap data from db.

		md5 -- beatmap md5
		return -- True if set, False if not set
		"""
		# Get data from DB
		data = objects.glob.db.fetch("SELECT * FROM beatmaps WHERE beatmap_md5 = %s LIMIT 1", [md5])

		# Make sure the query returned something
		if data is None:
			return False

		# Make sure the beatmap is not an old one
		if data["difficulty_taiko"] == 0 and data["difficulty_ctb"] == 0 and data["difficulty_mania"] == 0:
			log.debug("Difficulty for non-std gamemodes not found in DB, refreshing data from osu!api...")
			return False

		# Set cached data period
		expire = objects.glob.conf["BEATMAP_CACHE_EXPIRE"]

		# If the beatmap is ranked, we don't need to refresh data from osu!api that often
		if data["ranked"] >= rankedStatuses.RANKED and data["ranked_status_freezed"] == 0:
			expire *= 3

		# Make sure the beatmap data in db is not too old
		if int(expire) > 0 and time.time() > data["latest_update"]+int(expire) and not data["ranked_status_freezed"]:
			return False

		# Data in DB, set beatmap data
		log.debug("Got beatmap data from db")
		self.setDataFromDict(data)
		self.rating = data["rating"]	# db only, we don't want the rating from osu! api.
		return True

	def setDataFromDict(self, data):
		"""
		Set this object's beatmap data from data dictionary.

		data -- data dictionary
		return -- True if set, False if not set
		"""
		self.songName = data["song_name"]
		self.fileMD5 = data["beatmap_md5"]
		self.rankedStatus = int(data["ranked"])
		self.rankedStatusFrozen = int(data["ranked_status_freezed"])
		self.beatmapID = int(data["beatmap_id"])
		self.beatmapSetID = int(data["beatmapset_id"])
		self.AR = float(data["ar"])
		self.OD = float(data["od"])
		self.starsStd = float(data["difficulty_std"])
		self.starsTaiko = float(data["difficulty_taiko"])
		self.starsCtb = float(data["difficulty_ctb"])
		self.starsMania = float(data["difficulty_mania"])
		self.maxCombo = int(data["max_combo"])
		self.hitLength = int(data["hit_length"])
		self.bpm = int(data["bpm"])
		self.disablePP = bool(data["disable_pp"])
		# Ranking panel statistics
		self.playcount = int(data["playcount"]) if "playcount" in data else 0
		self.passcount = int(data["passcount"]) if "passcount" in data else 0

	def setDataFromOsuApi(self, md5, beatmapSetID):
		"""
		Set this object's beatmap data from osu!api.

		md5 -- beatmap md5
		beatmapSetID -- beatmap set ID, used to check if a map is outdated
		return -- True if set, False if not set
		"""
		# Check if osuapi is enabled
		mainData = None
		dataStd = osuapiHelper.osuApiRequest("get_beatmaps", "h={}&a=1&m=0".format(md5))
		dataTaiko = osuapiHelper.osuApiRequest("get_beatmaps", "h={}&a=1&m=1".format(md5))
		dataCtb = osuapiHelper.osuApiRequest("get_beatmaps", "h={}&a=1&m=2".format(md5))
		dataMania = osuapiHelper.osuApiRequest("get_beatmaps", "h={}&a=1&m=3".format(md5))
		if dataStd is not None:
			mainData = dataStd
		elif dataTaiko is not None:
			mainData = dataTaiko
		elif dataCtb is not None:
			mainData = dataCtb
		elif dataMania is not None:
			mainData = dataMania

		# If the beatmap is frozen and still valid from osu!api, return True so we don't overwrite anything
		if mainData is not None and self.rankedStatusFrozen == 1:
			return True

		# Can't fint beatmap by MD5. The beatmap has been updated. Check with beatmap set ID
		if mainData is None:
			log.debug("osu!api data is None")
			dataStd = osuapiHelper.osuApiRequest("get_beatmaps", "s={}&a=1&m=0".format(beatmapSetID))
			dataTaiko = osuapiHelper.osuApiRequest("get_beatmaps", "s={}&a=1&m=1".format(beatmapSetID))
			dataCtb = osuapiHelper.osuApiRequest("get_beatmaps", "s={}&a=1&m=2".format(beatmapSetID))
			dataMania = osuapiHelper.osuApiRequest("get_beatmaps", "s={}&a=1&m=3".format(beatmapSetID))
			if dataStd is not None:
				mainData = dataStd
			elif dataTaiko is not None:
				mainData = dataTaiko
			elif dataCtb is not None:
				mainData = dataCtb
			elif dataMania is not None:
				mainData = dataMania

			if mainData is None:
				# Still no data, beatmap is not submitted
				return False
			else:
				# We have some data, but md5 doesn't match. Beatmap is outdated
				self.rankedStatus = rankedStatuses.NEED_UPDATE
				return True


		# We have data from osu!api, set beatmap data
		log.debug("Got beatmap data from osu!api")
		self.songName = "{} - {} [{}]".format(mainData["artist"], mainData["title"], mainData["version"])
		self.fileName = "{} - {} ({}) [{}].osu".format(
			mainData["artist"], mainData["title"], mainData["creator"], mainData["version"]
		).replace("\\", "")
		self.fileMD5 = md5
		self.rankedStatus = convertRankedStatus(int(mainData["approved"]))
		self.beatmapID = int(mainData["beatmap_id"])
		self.beatmapSetID = int(mainData["beatmapset_id"])
		self.AR = float(mainData["diff_approach"])
		self.OD = float(mainData["diff_overall"])

		# Determine stars for every mode
		self.starsStd = 0.0
		self.starsTaiko = 0.0
		self.starsCtb = 0.0
		self.starsMania = 0.0
		if dataStd is not None:
			self.starsStd = float(dataStd.get("difficultyrating", 0))
		if dataTaiko is not None:
			self.starsTaiko = float(dataTaiko.get("difficultyrating", 0))
		if dataCtb is not None:
			self.starsCtb = float(
				next((x for x in (dataCtb.get("difficultyrating"), dataCtb.get("diff_aim")) if x is not None), 0)
			)
		if dataMania is not None:
			self.starsMania = float(dataMania.get("difficultyrating", 0))

		self.maxCombo = int(mainData["max_combo"]) if mainData["max_combo"] is not None else 0
		self.hitLength = int(mainData["hit_length"])
		if mainData["bpm"] is not None:
			self.bpm = int(float(mainData["bpm"]))
		else:
			self.bpm = -1
		return True

	def setData(self, md5, beatmapSetID):
		"""
		Set this object's beatmap data from highest level possible.

		md5 -- beatmap MD5
		beatmapSetID -- beatmap set ID
		"""
		# Get beatmap from db
		dbResult = self.setDataFromDB(md5)

		# Force refresh from osu api.
		# We get data before to keep frozen maps ranked
		# if they haven't been updated
		if dbResult and self.refresh:
			dbResult = False

		if not dbResult:
			log.debug("Beatmap not found in db")
			# If this beatmap is not in db, get it from osu!api
			apiResult = self.setDataFromOsuApi(md5, beatmapSetID)
			if not apiResult:
				# If it's not even in osu!api, this beatmap is not submitted
				self.rankedStatus = rankedStatuses.NOT_SUBMITTED
			elif self.rankedStatus != rankedStatuses.NOT_SUBMITTED and self.rankedStatus != rankedStatuses.NEED_UPDATE:
				# We get beatmap data from osu!api, save it in db
				self.addBeatmapToDB()
		else:
			log.debug("Beatmap found in db")

		log.debug("{}\n{}\n{}\n{}".format(self.starsStd, self.starsTaiko, self.starsCtb, self.starsMania))

	def getData(self, totalScores=0, version=4):
		"""
		Return this beatmap's data (header) for getscores

		return -- beatmap header for getscores
		"""
		rankedStatusOutput = self.rankedStatus

		# Force approved for A/Q/L beatmaps that give PP, so we don't get the alert in game
		if self.rankedStatus >= rankedStatuses.APPROVED and self.is_rankable:
			rankedStatusOutput = rankedStatuses.APPROVED

		# Fix loved maps for old clients
		if version < 4 and self.rankedStatus == rankedStatuses.LOVED:
			rankedStatusOutput = rankedStatuses.QUALIFIED

		data = "{}|false".format(rankedStatusOutput)
		if self.rankedStatus != rankedStatuses.NOT_SUBMITTED and self.rankedStatus != rankedStatuses.NEED_UPDATE and self.rankedStatus != rankedStatuses.UNKNOWN:
			# If the beatmap is updated and exists, the client needs more data
			data += "|{}|{}|{}\n{}\n{}\n{}\n".format(self.beatmapID, self.beatmapSetID, totalScores, self.offset, self.songName, self.rating)

		# Return the header
		return data

	@property
	def is_rankable(self):
		return self.rankedStatus >= rankedStatuses.RANKED \
			   and self.rankedStatus != rankedStatuses.UNKNOWN \
			   and not self.disablePP

	@property
	def is_mode_specific(self):
		return sum(x > 0 for x in (self.starsStd, self.starsTaiko, self.starsCtb, self.starsMania)) == 1

	@property
	def specific_game_mode(self):
		if not self.is_mode_specific:
			return None
		try:
			return next(
				mode for mode, pp in zip(
					(gameModes.STD, gameModes.TAIKO, gameModes.CTB, gameModes.MANIA),
					(self.starsStd, self.starsTaiko, self.starsCtb, self.starsMania)
				) if pp > 0
			)
		except StopIteration:
			# FUBAR beatmap 🤔
			return None

def convertRankedStatus(approvedStatus):
	"""
	Convert approved_status (from osu!api) to ranked status (for getscores)

	approvedStatus -- approved status, from osu!api
	return -- rankedStatus for getscores
	"""

	approvedStatus = int(approvedStatus)
	if approvedStatus <= 0:
		return rankedStatuses.PENDING
	elif approvedStatus == 1:
		return rankedStatuses.RANKED
	elif approvedStatus == 2:
		return rankedStatuses.APPROVED
	elif approvedStatus == 3:
		return rankedStatuses.QUALIFIED
	elif approvedStatus == 4:
		return rankedStatuses.LOVED
	else:
		return rankedStatuses.UNKNOWN

def incrementPlaycount(md5, passed):
	"""
	Increment playcount (and passcount) for a beatmap

	md5 -- beatmap md5
	passed -- if True, increment passcount too
	"""
	objects.glob.db.execute(
		f"UPDATE beatmaps "
		f"SET playcount = playcount+1{', passcount = passcount+1' if passed else ''} "
		f"WHERE beatmap_md5 = %s LIMIT 1",
		[md5]
	)
