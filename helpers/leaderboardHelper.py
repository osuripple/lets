from common.log import logUtils as log
from common.ripple import scoreUtils
from objects import glob
from common.ripple import userUtils

def getRankInfo(userID, gameMode):
	"""
	Get userID's current rank, user above us and pp/score difference

	:param userID: user
	:param gameMode: gameMode number
	:return: {"nextUsername": "", "difference": 0, "currentRank": 0}
	"""
	data = {"nextUsername": "", "difference": 0, "currentRank": 0}
	k = "ripple:leaderboard:{}".format(scoreUtils.readableGameMode(gameMode))
	position = userUtils.getGameRank(userID, gameMode) - 1
	log.debug("Our position is {}".format(position))
	if position is not None and position > 0:
		aboveUs = glob.redis.zrevrange(k, position - 1, position)
		log.debug("{} is above us".format(aboveUs))
		if aboveUs is not None and len(aboveUs) > 0 and aboveUs[0].isdigit():
			# Get our rank, next rank username and pp/score difference
			myScore = glob.redis.zscore(k, userID)
			otherScore = glob.redis.zscore(k, aboveUs[0])
			nextUsername = userUtils.getUsername(aboveUs[0])
			if nextUsername is not None and myScore is not None and otherScore is not None:
				data["nextUsername"] = nextUsername
				data["difference"] = int(myScore) - int(otherScore)
	else:
		position = 0

	data["currentRank"] = position + 1
	return data

def update(userID, newScore, gameMode):
	"""
	Update gamemode's leaderboard.
	Doesn't do anything if userID is banned/restricted.

	:param userID: user
	:param newScore: new score or pp
	:param gameMode: gameMode number
	"""
	if userUtils.isAllowed(userID):
		log.debug("Updating leaderboard...")
		glob.redis.zadd("ripple:leaderboard:{}".format(scoreUtils.readableGameMode(gameMode)), str(userID), str(newScore))
	else:
		log.debug("Leaderboard update for user {} skipped (not allowed)".format(userID))

def updateCountry(userID, newScore, gameMode):
	"""
	Update gamemode's country leaderboard.
	Doesn't do anything if userID is banned/restricted.

	:param userID: user, country is determined by the user
	:param newScore: new score or pp
	:param gameMode: gameMode number
	:return:
	"""
	if userUtils.isAllowed(userID):
		country = userUtils.getCountry(userID)
		if country is not None and len(country) > 0 and country.lower() != "xx":
			log.debug("Updating {} country leaderboard...".format(country))
			k = "ripple:leaderboard:{}:{}".format(scoreUtils.readableGameMode(gameMode), country.lower())
			glob.redis.zadd(k, str(userID), str(newScore))
	else:
		log.debug("Country leaderboard update for user {} skipped (not allowed)".format(userID))

def updateGlobalTopPPScoreID(gameMode):
	topPPLockKey = "ripple:top_pp_score_id_lock:{}".format(gameMode)
	log.debug("Updating global top pp for game mode {}".format(gameMode))
	if glob.redis.exists(topPPLockKey):
		log.warning("Top PP query is already executing")
		raise RuntimeError("Top PP query is already executing")
	try:
		glob.redis.set(topPPLockKey, 1, 120)		# lock for max 120 seconds
		# NOTE: We don't check if the map is ranked because it takes way too much time...
		topScore = glob.db.fetch(
			"SELECT scores.id FROM scores INNER JOIN users ON scores.userid = users.id "
			# "INNER JOIN beatmaps USING(beatmap_md5) "
			"WHERE play_mode = %s AND completed = 3 "
			# "AND ranked >= 2 "
			"AND users.privileges & 3 = 3 "
			"ORDER BY pp DESC LIMIT 1",
			(gameMode,)
		)
	finally:
		glob.redis.delete(topPPLockKey.format(gameMode))
	v = topScore["id"] if topScore is not None else 0
	setGlobalTopPPScoreID(gameMode, v)
	log.debug("Global top pp score id for game mode {} cached: {}".format(gameMode, v))

def setGlobalTopPPScoreID(gameMode, scoreID):
	glob.redis.set("ripple:top_pp_score_id:{}".format(gameMode), scoreID)
	glob.redis.delete("ripple:top_pp_score_id_lock:{}".format(gameMode))

def getGlobalTopPPScoreID(gameMode):
	r = glob.redis.get("ripple:top_pp_score_id:{}".format(gameMode))
	try:
		return int(r.decode())
	except (ValueError, AttributeError):
		return None
