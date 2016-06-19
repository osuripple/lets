import score
import glob
from helpers import userHelper
from constants import rankedStatuses

class scoreboard:
	def __init__(self, username, gameMode, beatmap, setScores = True):
		"""
		Initialize a leaderboard object

		username -- username of who's requesting the scoreboard. None if not known
		gameMode -- requested gameMode
		beatmap -- beatmap objecy relative to this leaderboard
		setScores -- if True, will get personal/top 50 scores automatically. Optional. Default: True
		"""
		self.scores = []				# list containing all score objects. First object is personal best
		self.personalBestRank = -1		# our personal best rank, -1 if not found yet
		self.username = username		# username of who's requesting the scoreboard. None if not known
		self.userID = userHelper.getID(self.username)	# username's userID
		self.gameMode = gameMode		# requested gameMode
		self.beatmap = beatmap			# beatmap objecy relative to this leaderboard
		if setScores == True:
			self.setScores()


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

		# Find personal best score
		if self.userID != 0:
			personalBestScore = glob.db.fetch("SELECT id FROM scores WHERE userid = %s AND beatmap_md5 = %s AND play_mode = %s AND completed = 3 ORDER BY score DESC LIMIT 1", [self.userID, self.beatmap.fileMD5, self.gameMode])
		else:
			personalBestScore = None

		# Output our personal best if found
		if personalBestScore != None:
			s = score.score(personalBestScore["id"])
			self.scores[0] = s
		else:
			# No personal best
			self.scores[0] = -1

		# Top 50 scores
		topScores = glob.db.fetchAll("SELECT * FROM scores LEFT JOIN users ON scores.userid = users.id WHERE scores.beatmap_md5 = %s AND scores.play_mode = %s AND scores.completed = 3 AND users.allowed = 1 ORDER BY score DESC LIMIT 50", [self.beatmap.fileMD5, self.gameMode])
		c = 1
		if topScores != None:
			for i in topScores:
				# Create score object
				s = score.score(i["id"], setData=False)

				# Set data and rank from topScores's row
				s.setDataFromDict(i)
				s.setRank(c)

				# Check if this top 50 score is our personal best
				if s.playerName == self.username:
					self.personalBestRank = c

				# Add this score to scores list and increment rank
				self.scores.append(s)
				c+=1

		# If personal best score was not in top 50, try to get it from cache
		if personalBestScore != None and self.personalBestRank < 1:
			self.personalBestRank = glob.personalBestCache.get(self.userID, self.beatmap.fileMD5)

		# It's not even in cache, get it from db
		if personalBestScore != None and self.personalBestRank < 1:
			self.setPersonalBest()

		# Cache our personal best rank so we can eventually use it later as
		# before personal best rank" in submit modular when building ranking panel
		if self.personalBestRank >= 1:
			glob.personalBestCache.set(self.userID, self.personalBestRank, self.beatmap.fileMD5)

	def setPersonalBest(self):
		"""
		Set personal best rank ONLY
		Ikr, that query is HUGE but xd
		"""
		# Before running the HUGE query, make sure we have a score on that map
		hasScore = glob.db.fetch("SELECT id FROM scores WHERE beatmap_md5 = %s AND userid = %s AND play_mode = %s AND completed = 3 LIMIT 1", [self.beatmap.fileMD5, self.userID, self.gameMode])
		if hasScore == None:
			return

		# We have a score, run the huge query
		result = glob.db.fetch("""SELECT COUNT(*) AS rank FROM scores LEFT JOIN users ON scores.userid = users.id WHERE scores.score >= (
		SELECT score FROM scores WHERE beatmap_md5 = %(md5)s AND play_mode = %(mode)s AND completed = 3 AND userid = %(userid)s
		) AND scores.beatmap_md5 = %(md5)s AND scores.play_mode = %(mode)s AND scores.completed = 3 AND users.allowed = 1 ORDER BY score DESC
		""", {"md5": self.beatmap.fileMD5, "userid": self.userID, "mode": self.gameMode})
		if result != None:
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
			# We have a personal best score
			if self.personalBestRank == -1:
				# ...but we don't know our rank in scoreboard. Get it.
				c=1
				self.userID = userHelper.getID(self.username)
				scores = glob.db.fetchAll("SELECT DISTINCT userid, score FROM scores WHERE beatmap_md5 = %s AND play_mode = %s AND completed = 3 ORDER BY score DESC", [self.beatmap.fileMD5, self.gameMode])
				if scores != None:
					for i in scores:
						if i["userid"] == self.userID:
							self.personalBestRank = c
						c+=1

			# Set personal best score rank
			self.scores[0].setRank(self.personalBestRank)
			data += self.scores[0].getData(self.username)

		# Output top 50 scores
		for i in self.scores[1:]:
			data += i.getData(self.username)

		return data
