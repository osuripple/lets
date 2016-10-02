from common.log import logUtils as log
from common.ripple import userUtils


class userStatsCache:
	def __init__(self):
		self.cache = [{}, {}, {}, {}]

	def get(self, userID, gameMode):
		"""
		Get cached user stats.
		If cached values are not found, they'll be read from db, cached and returned

		userID --
		gameMode -- gameMode number
		return -- userStats dictionary (rankedScore, totalScore, pp, accuracy, playcount)
		"""
		if userID not in self.cache[gameMode]:
			log.debug("userStatsCache miss")
			self.cache[gameMode][userID] = userUtils.getUserStats(userID, gameMode)
		log.debug("userStatsCache hit")
		return self.cache[gameMode][userID]

	def update(self, userID, gameMode, data = {}):
		"""
		Update cached user stats with new values

		userID --
		gameMode -- gameMode number
		data -- updated stats dictionary. Optional. If not passed, will get from db
		"""
		if len(data) == 0:
			data = userUtils.getUserStats(userID, gameMode)
		log.debug("userStatsCache set {}".format(data))
		self.cache[gameMode][userID] = data
