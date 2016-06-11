from helpers import consoleHelper
from constants import bcolors
from helpers import discordBotHelper

class invalidArgumentsException(Exception):
	def __init__(self, handler):
		consoleHelper.printColored("[{}] Invalid arguments".format(handler), bcolors.RED)

class loginFailedException(Exception):
	def __init__(self, handler, who):
		consoleHelper.printColored("[{}] {}'s Login failed".format(handler, who), bcolors.RED)

class userBannedException(Exception):
	def __init__(self, handler, who):
		consoleHelper.printColored("[{}] {} is banned".format(handler, who), bcolors.RED)

class noBanchoSessionException(Exception):
	def __init__(self, handler, who):
		consoleHelper.printColored("[{}] {} has no active bancho session".format(handler, who), bcolors.RED)
		discordBotHelper.sendConfidential("{username} has tried to submit a score without an active bancho session. If this happens ofter, {username} is trying to use a score submitter.".format(username=who))

class osuApiFailException(Exception):
	def __init__(self, handler):
		consoleHelper.printColored("[{}] Invalid data from osu!api".format(handler), bcolors.RED)

class fileNotFoundException(Exception):
	def __init__(self, handler, file):
		consoleHelper.printColored("[{}] File not found ({})".format(handler, file), bcolors.RED)

class invalidBeatmapException(Exception):
	pass

class beatmapTooLongException(Exception):
	def __init__(self, handler):
		consoleHelper.printColored("[{}] Requested beatmap is too long.".format(handler), bcolors.RED)

class fuck(Exception):
	pass
