STD = 0
TAIKO = 1
CTB = 2
MANIA = 3

def getGameModeForDB(gameMode):
	"""
	Convert a gamemode number to string for database table/column

	gameMode -- gameMode int or variable (ex: gameMode.std)
	return -- game mode readable string for db
	"""

	if gameMode == std:
		return "std"
	elif gameMode == taiko:
		return "taiko"
	elif gameMode == ctb:
		return "ctb"
	else:
		return "mania"


def getGamemodeFull(gameMode):
	if gameMode == STD:
		return "osu!"
	elif gameMode == TAIKO:
		return "Taiko"
	elif gameMode == CTB:
		return "Catch The Beat"
	else:
		return "osu!mania"