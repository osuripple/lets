from common.log import logUtils as log
from common.ripple import scoreUtils
from objects import glob


def getUserRank(userID, gameMode):
	"""
	Get userID's rank in gameMode's Leaderboard

	userID -- id of the user
	gameMode -- gameMode number
	return -- rank number. 0 if unknown
	"""
	mode = scoreUtils.readableGameMode(gameMode)
	result = glob.db.fetch("SELECT position FROM leaderboard_{} WHERE user = %s LIMIT 1".format(mode), [userID])
	if result is not None:
		return int(result["position"])
	else:
		return 0

def getRankInfo(userID, gameMode):
	"""
	userID --
	gameMode -- gameMode number
	return -- {"nextusername": string, "difference": int}
	"""
	data = {"nextUsername": "", "difference": 0, "currentRank": 0}
	modeForDB = scoreUtils.readableGameMode(gameMode)
	v = glob.db.fetch("SELECT v FROM leaderboard_{mode} WHERE user = %s LIMIT 1".format(mode=modeForDB), [userID])
	if v is not None:
		v = v["v"]
		result = glob.db.fetchAll("SELECT leaderboard_{mode}.*, users.username FROM leaderboard_{mode} LEFT JOIN users ON users.id = leaderboard_{mode}.user WHERE v >= %s ORDER BY v ASC LIMIT 2".format(mode=modeForDB), [v])
		if len(result) == 2:
			# Get us and other
			us = result[0]
			other = result[1]

			# Get our rank, next rank username and pp/score difference
			data["currentRank"] = us["position"]
			data["nextUsername"] = other["username"]
			data["difference"] = int(other["v"])-int(us["v"])

	return data

def update(userID, newScore, gameMode):
	"""
	Update gamemode's leaderboard the leaderboard

	userID --
	newScore -- new score or pp
	gameMode -- gameMode number
	"""
	log.debug("Updating leaderboard...")
	mode = scoreUtils.readableGameMode(gameMode)

	newPlayer = False
	us = glob.db.fetch("SELECT * FROM leaderboard_{} WHERE user=%s LIMIT 1".format(mode), [userID])
	if us is None:
		newPlayer = True

	# Find player who is right below our score
	target = glob.db.fetch("SELECT * FROM leaderboard_{} WHERE v <= %s ORDER BY position ASC LIMIT 1".format(mode), [newScore])
	plus = 0
	if target is None:
		# Wow, this user completely sucks at this game.
		target = glob.db.fetch("SELECT * FROM leaderboard_{} ORDER BY position DESC LIMIT 1".format(mode))
		plus = 1

	# Set newT
	if target is None:
		# Okay, nevermind. It's not this user to suck. It's just that no-one has ever entered the leaderboard thus far.
		# So, the player is now #1. Yay!
		newT = 1
	else:
		# Otherwise, just give them the position of the target.
		newT = target["position"] + plus

	# Make some place for the new "place holder".
	if newPlayer:
		glob.db.execute("UPDATE leaderboard_{} SET position = position + 1 WHERE position >= %s ORDER BY position DESC".format(mode), [newT])
	else:
		glob.db.execute("DELETE FROM leaderboard_{} WHERE user = %s".format(mode), [userID])
		glob.db.execute("UPDATE leaderboard_{} SET position = position + 1 WHERE position < %s AND position >= %s ORDER BY position DESC".format(mode), [us["position"], newT])

	#if newT <= 1:
	#	log.info("{} is now #{} ({})".format(userID, newT, mode), "bunker")

	# Finally, insert the user back.
	glob.db.execute("INSERT INTO leaderboard_{} (position, user, v) VALUES (%s, %s, %s);".format(mode), [newT, userID, newScore])
