from common.log import logUtils as log
from common.ripple import scoreUtils
from objects import glob
from common.ripple import userUtils

def getRankInfo(userID, gameMode):
	"""
	userID --
	gameMode -- gameMode number
	return -- {"nextUsername": "", "difference": 0, "currentRank": 0}
	"""
	data = {"nextUsername": "", "difference": 0, "currentRank": 0}
	k = "ripple:leaderboard:{}".format(scoreUtils.readableGameMode(gameMode))
	position = glob.redis.zrevrank(k, userID)
	log.debug("Our position is {}".format(position))
	if position is not None and position > 0:
		aboveUs = glob.redis.zrevrange(k, position - 1, position)
		log.debug("{} is above us".format(aboveUs))
		if aboveUs is not None and len(aboveUs) > 0 and aboveUs[0].isdigit():
			# Get our rank, next rank username and pp/score difference
			myScore = glob.redis.zscore(k, userID)
			otherScore = glob.redis.zscore(k, aboveUs[0])
			nextUsername = userUtils.getUsername(aboveUs[0])
			print(str(myScore))
			print(str(otherScore))
			print(str(nextUsername))
			if nextUsername is not None and myScore is not None and otherScore is not None:
				data["nextUsername"] = nextUsername
				data["difference"] = int(myScore) - int(otherScore)

	data["currentRank"] = position
	return data

def update(userID, newScore, gameMode):
	"""
	Update gamemode's leaderboard

	userID --
	newScore -- new score or pp
	gameMode -- gameMode number
	"""
	#log.debug("Updating leaderboard...")
	glob.redis.zadd("ripple:leaderboard:{}".format(scoreUtils.readableGameMode(gameMode)), str(userID), str(newScore))
