import string
import random
from datetime import datetime
import time
import hashlib
from functools import partial
from constants import mods
from time import gmtime, strftime

def randomString(length = 8):
	return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(length))

def stringToBool(s):
	"""
	Convert a string (True/true/1) to bool

	s -- string/int value
	return -- True/False
	"""
	return (s == "True" or s== "true" or s == "1" or s == 1)

def osuDateToUNIXTimestamp(osuDate):
	"""
	Convert an osu date to UNIX date

	osuDate -- osudate
	"""
	date_object = datetime.strptime(str(osuDate), "%y%m%d%H%M%S")
	unixtime = time.mktime(date_object.timetuple())
	unixtime = int(unixtime)
	return unixtime

def fileMd5(filename):
	"""
	Return filename's md5

	filename --
	return -- file md5
	"""
	with open(filename, mode='rb') as f:
		d = hashlib.md5()
		for buf in iter(partial(f.read, 128), b''):
			d.update(buf)
	return d.hexdigest()

def stringMd5(string):
	"""Return string's md5"""
	d = hashlib.md5()
	d.update(string.encode("utf-8"))
	return d.hexdigest()

def getRank(gameMode, __mods, acc, c300, c100, c50, cmiss):
	"""
	Return a string with rank/grade for a given score.
	Used mainly for "tillerino"

	gameMode -- mode (0 = osu!, 1 = Taiko, 2 = CtB, 3 = osu!mania)
	__mods -- mods bitwise number
	acc -- accuracy
	c300 -- 300 hit count
	c100 -- 100 hit count
	c50 -- 50 hit count
	cmiss -- miss count
	return -- rank/grade string
	"""
	print("start")
	total = c300 + c100 + c50 + cmiss
	hdfl = (__mods & mods.HIDDEN > 0) or (__mods & mods.FLASHLIGHT > 0)

	def ss():
		return "XH" if hdfl else "X"

	def s():
		return "SH" if hdfl else "S"

	if gameMode == 0:
		# osu!std
		if acc == 100:
			return ss()
		if c300 / total > 0.90 and c50 / total < 0.1 and cmiss == 0:
			return s()
		if (c300 / total > 0.80 and cmiss == 0) or (c300 / total > 0.90):
			return "A"
		if (c300 / total > 0.70 and cmiss == 0) or (c300 / total > 0.80):
			return "B"
		if c300 / total > 0.60:
			return "C"
		return "D"
	elif gameMode == 1:
		# taiko not implemented as of yet.
		return "A"
	elif gameMode == 2:
		# CtB
		if acc == 100:
			return ss()
		if acc >= 98.01 and acc <= 99.99:
			return s()
		if acc >= 94.01 and acc <= 98.00:
			return "A"
		if acc >= 90.01 and acc <= 94.00:
			return "B"
		if acc >= 98.01 and acc <= 90.00:
			return "C"
		return "D"
	elif gameMode == 3:
		# osu!mania
		if acc == 100:
			return ss()
		if acc > 95:
			return s()
		if acc > 90:
			return "A"
		if acc > 80:
			return "B"
		if acc > 70:
			return "C"
		return "D"

	return "A"


def getTimestamp():
	"""
	Return current time in YYYY-MM-DD HH:MM:SS format.
	Used in logs.
	"""
	return strftime("%Y-%m-%d %H:%M:%S", gmtime())
