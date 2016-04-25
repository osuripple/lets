import glob
from helpers import scoreHelper
from helpers import userHelper
from helpers import consoleHelper
from helpers import discordBotHelper
from constants import bcolors
import sys
import traceback
import time

def getUserRank(userID, gameMode):
	"""
	Get userID's rank in gameMode's Leaderboard

	userID -- id of the user
	gameMode -- gameMode number
	return -- rank number. 0 if unknown
	"""
	mode = scoreHelper.readableGameMode(gameMode)
	result = glob.db.fetch("SELECT position FROM leaderboard_{} WHERE user = ?;".format(mode), [userID])
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
			glob.db.execute("INSERT INTO leaderboard_{} (position, user, v) VALUES (?, ?, ?)".format(mode), [key + 1, value["user"], value["score"]])

def update(userID, newScore, gameMode):
	"""
	Schedule leaderboard update

	userID --
	newScore -- new score or pp
	gameMode -- gameMode number
	"""
	updates.append((userID, newScore, gameMode))

updates = []
def updateThread():
	while True:
		if len(updates) > 0:
			lastel = updates.pop()
			print("updating leaderboard for ", lastel[0])
			__actualUpdate(lastel[0], lastel[1], lastel[2])
		time.sleep(0.1)

def __actualUpdate(userID, newScore, gameMode):
	try:
		mode = scoreHelper.readableGameMode(gameMode)

		newPlayer = False
		us = glob.db.fetch("SELECT * FROM leaderboard_{} WHERE user=?".format(mode), [userID])
		if us == None:
			consoleHelper.printDebugMessage("New player")
			newPlayer = True

		# Find player who is right below our score
		target = glob.db.fetch("SELECT * FROM leaderboard_{} WHERE v <= ? ORDER BY position ASC LIMIT 1".format(mode), [newScore])
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
			glob.db.execute("UPDATE leaderboard_{} SET position = position + 1 WHERE position >= ? ORDER BY position DESC".format(mode), [newT])
		else:
			# logic for self:
			# Assume we have a leaderboard like the following:
			# 1. Howl
			# 2. Nyo
			# 3. avail
			# 4. Shaural
			# 5. marcostudios
			# We are avail and we have to take Howl's place.
			# target leaderboard:
			# 1. avail
			# 2. Howl
			# 3. Nyo
			# (same as before)
			# So what we do?
			# First thing, we get that Howl is the one right below or new score. e.g. Howl has 200pp, avail's old was 130, new's 230
			# Target position: target["position"] (1) + plus (0) = 1
			# So we first delete us from the leaderboard
			# then we get all the users in the range 1..2 (target user..current position - 1)
			# and then we insert us back.
			glob.db.execute("DELETE FROM leaderboard_{} WHERE user = ?".format(mode), [userID])
			glob.db.execute("UPDATE leaderboard_{} SET position = position + 1 WHERE position < ? AND position >= ? ORDER BY position DESC".format(mode), [us["position"], newT])

		if newT <= 1:
			discordBotHelper.sendConfidential("{} is now #{}".format(userID, newT))

		# Finally, insert the user back.
		glob.db.execute("INSERT INTO leaderboard_{} (position, user, v) VALUES (?, ?, ?);".format(mode), [newT, userID, newScore])
	except:
		discordBotHelper.sendConfidential("Error while updating the leaderboard: {}".format(sys.exc_info()))
		discordBotHelper.sendConfidential("Traceback: {}".format(traceback.format_exc()))
		consoleHelper.printColored("[!] Error while updating leaderboard!", bcolors.RED)
