from objects import score
from common.ripple import userUtils
from constants import rankedStatuses
from common.constants import mods as modsEnum
from objects import glob


class scoreboard:
	def __init__(
		self, username, gameMode, beatmap, setScores = True,
		country = False, friends = False, mods = -1, relax = False
	):
		"""
		Initialize a leaderboard object

		username -- username of who's requesting the scoreboard. None if not known
		gameMode -- requested gameMode
		beatmap -- beatmap object relative to this leaderboard
		setScores -- if True, will get personal/top 50 scores automatically. Optional. Default: True
		"""
		self.scores = []				# list containing all top 50 scores objects. First object is personal best
		self.totalScores = 0
		self.personalBestRank = -1		# our personal best rank, -1 if not found yet
		self.personalBestDone = False
		self.username = username		# username of who's requesting the scoreboard. None if not known
		self.userID = userUtils.getID(self.username)	# username's userID
		self.gameMode = gameMode		# requested gameMode
		self.beatmap = beatmap			# beatmap objecy relative to this leaderboard
		self.country = country
		self.friends = friends
		self.mods = mods
		self.isRelax = relax
		if setScores:
			self.setScores()

	@staticmethod
	def buildQuery(params):
		return "{select} {joins} {country} {mods} {friends} {order} {limit}".format(**params)

	def getPersonalBestID(self):
		if self.userID == 0:
			return None

		# Query parts
		cdef str select = ""
		cdef str joins = ""
		cdef str country = ""
		cdef str mods = ""
		cdef str friends = ""
		cdef str order = ""
		cdef str limit = ""
		select = "SELECT id FROM scores " \
				 "WHERE beatmap_md5 = %(md5)s " \
				 "AND is_relax = %(isRelax)s " \
				 "AND play_mode = %(mode)s " \
				 "AND completed = 3 " \
				 "AND userid = %(userid)s "

		# Mods
		if self.mods > -1:
			mods = "AND mods = %(mods)s"

		# Friends ranking
		if self.friends:
			friends = "AND (scores.userid IN (" \
					  "SELECT user2 FROM users_relationships " \
					  "WHERE user1 = %(userid)s) " \
					  "OR scores.userid = %(userid)s" \
					  ")"

		# was 'ORDER BY score DESC'. Shouldn't be needed, because completed = 3 is already the max score/pp
		order = ""
		limit = "LIMIT 1"

		# Build query, get params and run query
		query = self.buildQuery(locals())
		id_ = glob.db.fetch(query, {
			"userid": self.userID,
			"md5": self.beatmap.fileMD5,
			"mode": self.gameMode,
			"mods": self.mods,
			"isRelax": self.isRelax
		})
		if id_ is None:
			return None
		return id_["id"]

	def setScores(self):
		"""
		Set scores list
		"""
		# Reset score list
		self.scores = []
		self.scores.append(-1)

		# Make sure the beatmap is ranked
		if self.beatmap.rankedStatus < rankedStatuses.RANKED:
			return

		# Query parts
		cdef str select = ""
		cdef str joins = ""
		cdef str country = ""
		cdef str mods = ""
		cdef str friends = ""
		cdef str order = ""
		cdef str limit = ""

		# Find personal best score
		personalBestScoreID = self.getPersonalBestID()

		# Output our personal best if found
		if personalBestScoreID is not None:
			s = score.score(personalBestScoreID)
			self.scores[0] = s
		else:
			# No personal best
			self.scores[0] = -1

		# Get top 50 scores
		select = "SELECT *"
		if self.country:
			join_stats = "JOIN users_stats ON users.id = users_stats.id"
		else:
			join_stats = ""
		joins = "FROM scores JOIN users " \
				"ON scores.userid = users.id " \
				f" {join_stats} " \
				"WHERE scores.beatmap_md5 = %(beatmap_md5)s " \
				"AND scores.is_relax = %(isRelax)s " \
				"AND scores.play_mode = %(play_mode)s " \
				"AND scores.completed = 3 " \
				"AND (users.is_public = 1 OR users.id = %(userid)s)"

		# Country ranking
		if self.country:
			country = "AND users_stats.country = (SELECT country FROM users_stats WHERE id = %(userid)s LIMIT 1)"
		else:
			country = ""

		# Mods ranking (ignore auto, since we use it for pp sorting)
		if self.mods > -1 and self.mods & modsEnum.AUTOPLAY == 0:
			mods = "AND scores.mods = %(mods)s"
		else:
			mods = ""

		# Friends ranking
		if self.friends:
			friends = "AND (scores.userid IN (" \
					  "SELECT user2 FROM users_relationships " \
					  "WHERE user1 = %(userid)s) " \
					  "OR scores.userid = %(userid)s" \
					  ")"
		else:
			friends = ""

		# Sort and limit at the end
		if self.mods <= -1 or self.mods & modsEnum.AUTOPLAY == 0:
			# Order by score if we aren't filtering by mods or autoplay mod is disabled
			order = "ORDER BY score DESC"
		elif self.mods & modsEnum.AUTOPLAY > 0:
			# Otherwise, filter by pp
			order = "ORDER BY pp DESC"
		limit = "LIMIT 50"

		# Build query, get params and run query
		query = self.buildQuery(locals())
		params = {
			"beatmap_md5": self.beatmap.fileMD5,
			"play_mode": self.gameMode,
			"userid": self.userID,
			"mods": self.mods,
			"isRelax": int(self.isRelax)
		}
		topScores = glob.db.fetchAll(query, params)

		# Set data for all scores
		cdef dict topScore
		cdef int c = 1
		# for c, topScore in enumerate(topScores):
		for topScore in topScores:
			# Create score object
			s = score.score(topScore["id"], setData=False)

			# Set data and rank from topScores's row
			s.setDataFromDict(topScore)
			s.rank = c

			# Check if this top 50 score is our personal best
			if s.playerName == self.username:
				self.personalBestRank = c

			# Add this score to scores list and increment rank
			self.scores.append(s)
			c += 1

		# If we have more than 50 scores, run query to get scores count
		if c >= 50:
			# Count all scores on this map and do not order
			select = "SELECT COUNT(*) AS count"
			order = ""
			limit = "LIMIT 1"

			# Build query, get params and run query
			query = self.buildQuery(locals())
			count = glob.db.fetch(query, params)
			self.totalScores = 0 if count is None else count["count"]
		else:
			self.totalScores = c-1

		# If personal best score was not in top 50, try to get it from cache
		if personalBestScoreID is not None and self.personalBestRank < 1:
			self.personalBestRank = glob.personalBestCache.get(
				self.userID,
				self.beatmap.fileMD5,
				self.country,
				self.friends,
				self.mods
			)

		# It's not even in cache, get it from db
		if personalBestScoreID is not None and self.personalBestRank < 1:
			self.setPersonalBestRank()

		# Cache our personal best rank so we can eventually use it later as
		# before personal best rank" in submit modular when building ranking panel
		if self.personalBestRank >= 1:
			glob.personalBestCache.set(self.userID, self.personalBestRank, self.beatmap.fileMD5, relax=self.isRelax)

	def setPersonalBestRank(self):
		# Before running the HUGE query, make sure we have a score on that map
		cdef str query = "SELECT id FROM scores " \
						 "WHERE beatmap_md5 = %(md5)s " \
						 "AND is_relax = %(isRelax)s " \
						 "AND play_mode = %(mode)s " \
						 "AND completed = 3 " \
						 "AND userid = %(userid)s "
		# Mods
		if self.mods > -1:
			query += " AND scores.mods = %(mods)s"
		# Friends ranking
		if self.friends:
			query += " AND (scores.userid IN (" \
					 "SELECT user2 FROM users_relationships " \
					 "WHERE user1 = %(userid)s) " \
					 "OR scores.userid = %(userid)s" \
					 ")"
		# Sort and limit at the end
		query += " LIMIT 1"
		hasScore = glob.db.fetch(
			query,
			{
				"md5": self.beatmap.fileMD5,
				"userid": self.userID,
				"mode": self.gameMode,
				"mods": self.mods,
				"isRelax": int(self.isRelax)
			}
		)
		if hasScore is None:
			return

		# We have a score, run the huge query
		# Base query
		if self.country:
			join_stats = "JOIN users_stats ON users.id = users_stats.id"
		else:
			join_stats = ""
		query = f"""SELECT COUNT(*) AS rank FROM scores
		JOIN users ON scores.userid = users.id
		{join_stats}
		WHERE scores.score >= (
			SELECT score FROM scores
			WHERE beatmap_md5 = %(md5)s
			AND scores.is_relax = %(isRelax)s
			AND play_mode = %(mode)s
			AND completed = 3
			AND userid = %(userid)s
			LIMIT 1
		)
		AND scores.beatmap_md5 = %(md5)s
		AND scores.is_relax = %(isRelax)s
		AND scores.play_mode = %(mode)s
		AND scores.completed = 3
		AND (users.is_public = 1 OR users.id = %(userid)s)"""
		# Country
		if self.country:
			query += " AND users_stats.country = (SELECT country FROM users_stats WHERE id = %(userid)s LIMIT 1)"
		# Mods
		if self.mods > -1:
			query += " AND scores.mods = %(mods)s"
		# Friends
		if self.friends:
			query += " AND (scores.userid IN (" \
					 "SELECT user2 FROM users_relationships " \
					 "WHERE user1 = %(userid)s) " \
					 "OR scores.userid = %(userid)s" \
					 ")"
		# Sort and limit at the end
		query += " ORDER BY score DESC LIMIT 1"
		result = glob.db.fetch(
			query,
			{
				"md5": self.beatmap.fileMD5,
				"userid": self.userID,
				"mode": self.gameMode,
				"mods": self.mods,
				"isRelax": self.isRelax
			}
		)
		self.personalBestDone = True
		if result is not None:
			self.personalBestRank = result["rank"]

	def getScoresData(self):
		"""
		Return scores data for getscores

		return -- score data in getscores format
		"""
		data = ""

		# Output personal best
		if self.scores[0] == -1:
			# We don't have a personal best score
			data += "\n"
		else:
			# Set personal best score rank
			if not self.personalBestDone:
				self.setPersonalBestRank()	# sets self.personalBestRank with the huge query
			self.scores[0].rank = self.personalBestRank
			data += self.scores[0].getData()

		# Output top 50 scores
		for i in self.scores[1:]:
			data += i.getData(pp=self.mods > -1 and self.mods & modsEnum.AUTOPLAY > 0)

		return data
