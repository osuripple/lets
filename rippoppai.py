import subprocess
import os
from helpers import scoreHelper
from helpers import osuapiHelper
from constants import exceptions
from helpers import consoleHelper
from constants import bcolors
from helpers import generalHelper
import score
import beatmap
import argparse

import threading
import signal

MODULE_NAME = "rippoppai"
UNIX = True if os.name == "posix" else False

def fixPath(command):
	"""
	Replace / with \ if running under WIN32

	commnd -- command to fix
	return -- command with fixed paths
	"""
	if UNIX == True:
		return command
	return command.replace("/", "\\")

class oppai:
	OPPAI_FOLDER = "../oppai"

	def __init__(self, __beatmap, __score):
		# Params
		self.score = __score
		self.beatmap = __beatmap
		self.map = "{}.osu".format(self.beatmap.beatmapID)
		self.acc = self.score.accuracy*100
		self.mods = scoreHelper.readableMods(self.score.mods)
		self.combo = self.score.maxCombo
		self.misses = self.score.cMiss
		self.pp = 0
		self.getPP()

	def getPP(self):
		"""
		Calculate total pp value and return it

		return -- total pp
		"""
		try:
			# Build .osu file path
			mapFile = "{path}/maps/{map}".format(path=self.OPPAI_FOLDER, map=self.map)

			try:
				# Check if we have to download the file
				download = False
				if not os.path.isfile(mapFile):
					# .osu file doesn't exist. We must download it
					consoleHelper.printColored("[!] {} doesn't exist".format(mapFile), bcolors.YELLOW)
					download = True
				else:
					# File exists, check md5
					if generalHelper.fileMd5(mapFile) != self.beatmap.fileMD5:
						consoleHelper.printColored("[!] Beatmaps md5 don't match".format(mapFile), bcolors.YELLOW)
						download = True

				# Download .osu file if needed
				if download == True:
					consoleHelper.printRippoppaiMessage("Downloading {} from osu! servers...".format(mapFile))

					# Get .osu file from osu servers
					fileContent = osuapiHelper.getOsuFileFromID(self.beatmap.beatmapID)

					# Make sure osu servers returned something
					if fileContent == None:
						raise exceptions.osuApiFailException(MODULE_NAME)

					# Delete old .osu file if it exists
					if os.path.isfile(mapFile):
						os.remove(mapFile)

					# Save .osu file
					with open(mapFile, "wb+") as f:
						f.write(fileContent.encode("latin-1"))
				else:
					# Map file is already in folder
					consoleHelper.printRippoppaiMessage("Found beatmap file {}".format(mapFile))
			except exceptions.osuApiFailException:
				pass

			# Command
			command = fixPath("{path}/oppai {mapFile} {acc}% +{mods} {combo}x {misses}xm".format(path=self.OPPAI_FOLDER, mapFile=mapFile, acc=self.acc, mods=self.mods, combo=self.combo, misses=self.misses))
			consoleHelper.printRippoppaiMessage("Executing {}".format(command))

			# Output
			#output = oppaiThread(command, 3).Run()
			process = subprocess.run(command, shell=True, stdout=subprocess.PIPE)
			output = process.stdout.decode("utf-8")

			# Last output line
			pp = output.split("\r\n")
			pp = pp[len(pp)-2][:-2]
			self.pp = float(pp)
			consoleHelper.printRippoppaiMessage("PP: {}".format(self.pp))
			return self.pp
		except:
			consoleHelper.printColored("[!] Error while executing oppai.", bcolors.RED)
			raise


if __name__ == "__main__":
	# Standalone imports
	import glob
	from helpers import config
	from helpers import databaseHelper
	from constants import rankedStatuses
	import sys

	def recalcFromScoreID(scoreID):
		"""
		Recalculate pp value for scoreID.
		Does every check, output and queries needed.

		scoreID -- id of score to recalc
		return -- True if success, False if failed
		"""

		# Create score object and set its data
		s = score.score()
		s.setDataFromDB(scoreID)
		if s.scoreID == 0:
			# Make sure the score exists
			consoleHelper.printColored("[!] No score with id {}".format(scoreID), bcolors.RED)
			return False

		# Create beatmap object and set its data
		b = beatmap.beatmap()
		b.setData(s.fileMd5, 0)
		if b.rankedStatus != rankedStatuses.RANKED and b.rankedStatus != rankedStatuses.APPROVED and b.rankedStatus != rankedStatuses.QUALIFIED:
			# Make sure the beatmap is ranked
			consoleHelper.printColored("[!] Beatmap {} is not ranked ({}).".format(s.fileMd5, b.rankedStatus), bcolors.RED)
			return False

		# Calculate score pp
		s.calculatePP(b)

		# Update score pp
		try:
			glob.db.execute("UPDATE scores SET pp = ? WHERE id = ?", [s.pp, s.scoreID])
		except:
			consoleHelper.printColored("[!] Error while executing query", bcolors.RED)
			return False
		return True

	def massRecalc(scores):
		"""
		Recalc pp for scores in scores dictionary.

		scores -- dictionary returned from query. must contain id key with score id
		"""
		if scores != None:
			tot = len(scores)
			print("Found {} scores".format(tot))
			c = 1
			for i in scores:
				recalcFromScoreID(i["id"])
				consoleHelper.printColored("{}/{} ({:.2f}%)".format(c, tot, (100*c)/tot), bcolors.YELLOW)
				c+=1

	# CLI stuff
	__author__ = "Nyo"
	parser = argparse.ArgumentParser(description="pp calculator for ripple 2 / LETS")
	parser.add_argument('-r','--recalc', help="recalculate pp for every score (std scores only)", required=False, action='store_true')
	parser.add_argument('-z','--zero', help="calculate pp for 0 pp scores (std scores only)", required=False, action='store_true')
	parser.add_argument('-i','--id', help="calculate pp for score with this id", required=False)
	parser.add_argument('-m','--mods', help="calculate pp for scores with this mod (id)", required=False)
	parser.add_argument('-v','--verbose', help="run ripp in verbose mode", required=False, action='store_true')
	args = parser.parse_args()

	# Platform
	print("Running under {}".format("UNIX" if UNIX == True else "WIN32"))

	# Load config
	consoleHelper.printNoNl("> Reading config file... ")
	glob.conf = config.config("config.ini")
	consoleHelper.printDone()

	# Connect to MySQL
	try:
		consoleHelper.printNoNl("> Connecting to MySQL db... ")
		glob.db = databaseHelper.db(glob.conf.config["db"]["host"], glob.conf.config["db"]["username"], glob.conf.config["db"]["password"], glob.conf.config["db"]["database"], 0)
		consoleHelper.printDone()
	except:
		consoleHelper.printError()
		consoleHelper.printColored("[!] Error while connection to database. Please check your config.ini and run the server again", bcolors.RED)
		raise

	# Operations
	if args.zero == True:
		# 0pp recalc
		print("> Recalculating pp for zero-pp scores")
		scores = glob.db.fetchAll("SELECT id FROM scores WHERE pp = 0 AND play_mode = 0 AND completed = 3")
		massRecalc(scores)
	elif args.recalc == True:
		# Full recalc
		print("> Recalculating pp for every scores")
		scores = glob.db.fetchAll("SELECT id FROM scores WHERE play_mode = 0 AND completed = 3")
		massRecalc(scores)
	elif args.mods != None:
		# Mods recalc
		print("> Recalculating pp for scores with mods {}".format(args.mods))
		allScores = glob.db.fetchAll("SELECT id, mods FROM scores WHERE pp = 0 AND play_mode = 0 AND completed = 3")
		scores = []
		for i in allScores:
			if i["mods"] & int(args.mods) > 0:
				consoleHelper.printColored("> PP for score {} will be recalculated (mods: {})".format(i["id"], i["mods"]), bcolors.GREEN)
				scores.append(i)
		massRecalc(scores)
	elif args.id != None:
		# ID recalc
		recalcFromScoreID(args.id)

	consoleHelper.printColored("Done!", bcolors.GREEN)

	# Some test values
	'''b = beatmap.beatmap("d7e1002824cb188bf318326aa109469d", 0)
	s = score.score()
	s.c300 = 1150
	s.c100 = 22
	s.c50 = 0
	s.cKatu = 244
	s.cGeki = 16
	s.cMiss = 1
	s.maxCombo = 1769
	s.mods = 64
	s.calculateAccuracy()
	o = oppai(b, s)
	print(str(o.pp))'''
