from common.constants import mods


def isRankable(m):
	"""
	Return True if there are no unranked mods, otherwise False

	m -- mods to check
	return -- True if rankable, False if not rankable
	"""
	return not ((m & mods.RELAX > 0) or (m & mods.RELAX2 > 0) or (m & mods.AUTOPLAY > 0))

def readableGameMode(gameMode):
	"""
	Convert numeric gameMode to a readable format. Can be used for db too

	gameMode -- gameMode number
	"""
	if gameMode == 0:
		return "std"
	elif gameMode == 1:
		return "taiko"
	elif gameMode == 2:
		return "ctb"
	else:
		return "mania"

def readableMods(__mods):
	"""
	Return a string with readable std mods.
	Used to convert a mods number for oppai

	__mods -- mods bitwise number
	return -- readable mods string, eg HDDT
	"""
	r = ""
	if __mods == 0:
		return "nomod"

	if __mods & mods.NOFAIL > 0:
		r += "NF"
	if __mods & mods.EASY > 0:
		r += "EZ"
	if __mods & mods.HIDDEN > 0:
		r += "HD"
	if __mods & mods.HARDROCK > 0:
		r += "HR"
	if __mods & mods.DOUBLETIME > 0:
		r += "DT"
	if __mods & mods.HALFTIME > 0:
		r += "HT"
	if __mods & mods.FLASHLIGHT > 0:
		r += "FL"
	if __mods & mods.SPUNOUT > 0:
		r += "SO"

	return r