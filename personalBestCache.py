from common.log import logUtils as log


class personalBestCache:
	def __init__(self):
		# Key: 		userID,
		# Value: 	(personalBestRank, fileMd5, country, friends, mods)
		self.cache = {}

	def get(self, userID, fileMd5, country=False, friends=False, mods=-1):
		"""
		Get cached personal best rank.

		userID --
		fileMd5 -- beatmap md5
		return -- 	cached personal best rank if fileMd5 match,
					0 if fileMd5 is different or user not found in cache
		"""
		try:
			# Make sure the value is in cache
			if userID not in self.cache:
				raise
			# Unpack cache tuple
			cachedpersonalBestRank, cachedfileMd5, cachedCountry, cachedFriends, cachedMods = self.cache[userID]
			# Check if everything matches
			if fileMd5 != cachedfileMd5 or country != cachedCountry or friends != cachedFriends or mods != cachedMods:
				raise
			# Cache hit
			log.debug("personalBestCache hit")
			return self.cache[userID][0]
		except:
			log.debug("personalBestCache miss")
			return 0

	def set(self, userID, rank, fileMd5, country=False, friends=False, mods=-1):
		"""
		Update cached personal best rank value

		userID --
		rank -- new rank
		fileMd5 -- beatmap md5
		"""
		self.cache[userID] = (rank, fileMd5, country, friends, mods)
		log.debug("personalBestCache set {}".format(self.cache[userID]))
