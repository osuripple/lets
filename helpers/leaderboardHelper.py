import glob
from helpers import scoreHelper
from helpers import userHelper
from helpers import logHelper as log
import sys
import traceback

def getUserRank(userID, gameMode):
	"""
	Get userID's rank in gameMode's Leaderboard

	userID -- id of the user
	gameMode -- gameMode number
	return -- rank number. 0 if unknown
	"""
	mode = scoreHelper.readableGameMode(gameMode)
	result = glob.db.fetch("SELECT position FROM leaderboard_{} WHERE user = %s;".format(mode), [userID])
	if result != None:
		return result
	else:
		return 0

def build():
	"""
	Build the leaderboard for every gamemode

	WARNING: THIS FUNCTION WAS NOT TESTED
	"""
	# Declare stuff that will be used later on.
	modes = ["std", "taiko", "ctb", "mania"]
	data = {"std": [], "taiko": [], "ctb": [], "mania": []}
	allowedUsers = userHelper.getAllowedUsers('id')

	# Get all user's stats (ranked scores or pp)
	ranking = "pp" if glob.pp == True else "ranked_score"
	users = glob.db.fetchAll("SELECT id, {ranking}_std, {ranking}_taiko, {ranking}_ctb, {ranking}_mania FROM users_stats".format(ranking=rannking))

	# Put the data in the correct way into the array.
	for user in users:
		if allowedUsers[user["id"]] == False:
			continue

		for mode in modes:
			data[mode].append({"user": user["id"], "score": user["{}_{}".format(ranking, mode)]})

	# We're doing the sorting for every mode.
	for mode in modes:
		# Do the sorting
		data[mode].sort(key=lambda s: s["score"])

		# Remove all data from the table
		glob.db.execute("TRUNCATE TABLE leaderboard_{};".format(mode))

		# And insert each user.
		for key, value in data[mode]:
			glob.db.execute("INSERT INTO leaderboard_{} (position, user, v) VALUES (%s, %s, %s)".format(mode), [key + 1, value["user"], value["score"]])

def update(userID, newScore, gameMode):
	"""
	Update gamemode's leaderboard the leaderboard

	userID --
	newScore -- new score or pp
	gameMode -- gameMode number
	"""
	try:
		mode = scoreHelper.readableGameMode(gameMode)

		newPlayer = False
		us = glob.db.fetch("SELECT * FROM leaderboard_{} WHERE user=%s".format(mode), [userID])
		if us == None:
			newPlayer = True

		# Find player who is right below our score
		target = glob.db.fetch("SELECT * FROM leaderboard_{} WHERE v <= %s ORDER BY position ASC LIMIT 1".format(mode), [newScore])
		plus = 0
		if target == None:
			# Wow, this user completely sucks at this game.
			target = glob.db.fetch("SELECT * FROM leaderboard_{} ORDER BY position DESC LIMIT 1".format(mode))
			plus = 1

		# Set $newT
		if target == None:
			# Okay, nevermind. It's not this user to suck. It's just that no-one has ever entered the leaderboard thus far.
			# So, the player is now #1. Yay!
			newT = 1
		else:
			# Otherwise, just give them the position of the target.
			newT = target["position"] + plus

		# Make some place for the new "place holder".
		if newPlayer == True:
			glob.db.execute("UPDATE leaderboard_{} SET position = position + 1 WHERE position >= %s ORDER BY position DESC".format(mode), [newT])
		else:
			glob.db.execute("DELETE FROM leaderboard_{} WHERE user = %s".format(mode), [userID])
			glob.db.execute("UPDATE leaderboard_{} SET position = position + 1 WHERE position < %s AND position >= %s ORDER BY position DESC".format(mode), [us["position"], newT])

		if newT <= 1:
			log.info("{} is now #{} ({})".format(userID, newT, mode), True)

		# Finally, insert the user back.
		glob.db.execute("INSERT INTO leaderboard_{} (position, user, v) VALUES (%s, %s, %s);".format(mode), [newT, userID, newScore])
	except:
		msg = "Unknown error while updating the leaderboard!\n```{}\n{}```".format(sys.exc_info(), traceback.format_exc())
		log.error("{}".format(msg), True)
