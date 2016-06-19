from helpers import userHelper
from helpers import logHelper as log

class personalBestCache:
	def __init__(self):
		# Key: 		userID,
		# Value: 	(personalBestRank, fileMd5)
		self.cache = {}

	def get(self, userID, fileMd5):
		"""
		Get cached personal best rank.

		userID --
		fileMd5 -- beatmap md5
		return -- 	cached personal best rank if fileMd5 match,
					0 if fileMd5 is different or user not found in cache
		"""
		if userID not in self.cache or self.cache[userID][1] != fileMd5:
			log.debug("personalBestCache miss")
			return 0
		log.debug("personalBestCache hit")
		return self.cache[userID][0]

	def set(self, userID, rank, fileMd5):
		"""
		Update cached personal best rank value

		userID --
		rank -- new rank
		fileMd5 -- beatmap md5
		"""
		self.cache[userID] = (rank, fileMd5)
		log.debug("personalBestCache set {}".format(self.cache[userID]))
