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
		uid = userHelper.getID(self.username)
		if uid != 0:
			personalBestScore = glob.db.fetch("SELECT id FROM scores WHERE userid = %s AND beatmap_md5 = %s AND play_mode = %s AND completed = 3 ORDER BY score DESC LIMIT 1", [uid, self.beatmap.fileMD5, self.gameMode])
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
		topScores = glob.db.fetchAll("SELECT scores.id AS id FROM scores LEFT JOIN users ON scores.userid = users.id WHERE beatmap_md5 = %s AND play_mode = %s AND completed = 3 AND users.allowed = '1' ORDER BY score DESC", [self.beatmap.fileMD5, self.gameMode])
		c = 1
		if topScores != None:
			for i in topScores:
				# Get only first 50 scores
				if c > 50:
					break

				# Create score object and set its data
				s = score.score(i["id"], c)

				# Check if this top 50 score is our personal best
				if s.playerName == self.username:
					self.personalBestRank = c

				# Add this score to scores list and increment rank
				self.scores.append(s)
				c+=1


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
				uid = userHelper.getID(self.username)
				scores = glob.db.fetchAll("SELECT DISTINCT userid FROM scores WHERE beatmap_md5 = %s AND play_mode = %s AND completed = 3 ORDER BY score DESC", [self.beatmap.fileMD5, self.gameMode])
				if scores != None:
					for i in scores:
						if i["userid"] == uid:
							self.personalBestRank = c
						c+=1

			# Set personal best score rank
			self.scores[0].setRank(self.personalBestRank)
			data += self.scores[0].getData(self.username)

		# Output top 50 scores
		for i in self.scores[1:]:
			data += i.getData(self.username)

		return data
