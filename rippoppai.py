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
import math
import time

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
					#consoleHelper.printColored("[!] {} doesn't exist".format(mapFile), bcolors.YELLOW)
					download = True
				else:
					# File exists, check md5
					if generalHelper.fileMd5(mapFile) != self.beatmap.fileMD5:
						#consoleHelper.printColored("[!] Beatmaps md5 don't match".format(mapFile), bcolors.YELLOW)
						download = True

				# Download .osu file if needed
				if download == True:
					#consoleHelper.printRippoppaiMessage("Downloading {} from osu! servers...".format(mapFile))

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
					#consoleHelper.printRippoppaiMessage("Found beatmap file {}".format(mapFile))
					pass
			except exceptions.osuApiFailException:
				pass

			# Command
			command = fixPath("{path}/oppai {mapFile} {acc}% +{mods} {combo}x {misses}xm".format(path=self.OPPAI_FOLDER, mapFile=mapFile, acc=self.acc, mods=self.mods, combo=self.combo, misses=self.misses))
			#consoleHelper.printRippoppaiMessage("Executing {}".format(command))

			# Output
			#output = oppaiThread(command, 3).Run()
			process = subprocess.run(command, shell=True, stdout=subprocess.PIPE)
			output = process.stdout.decode("utf-8")

			# Last output line
			pp = output.split("\r\n" if UNIX == False else "\n")
			pp = pp[len(pp)-2][:-2]
			self.pp = float(pp)
			#consoleHelper.printRippoppaiMessage("PP: {}".format(self.pp))
			return self.pp
		except:
			consoleHelper.printColored("[!] Error while executing oppai.", bcolors.RED)
			self.pp = 0


if __name__ == "__main__":
	# Standalone imports
	import glob
	from helpers import config
	from helpers import databaseHelper
	from constants import rankedStatuses
	import sys

	def recalcFromScoreData(scoreData, lock):
		"""
		Recalculate pp value for a score.
		Does every check, output and queries needed.

		score -- score dictionary of score to recalc
		lock -- shared lock object
		return -- calculated pp value or None
		"""

		# Create score object and set its data
		s = score.score()
		s.setDataFromDict(scoreData)
		if s.scoreID == 0:
			# Make sure the score exists
			consoleHelper.printColored("[!] No score with id {}".format(scoreData["id"]), bcolors.RED)

		# Create beatmap object
		b = beatmap.beatmap()

		# Check if we have data for this song
		if scoreData["song_name"] == None:
			# If we don't have song data in scoreData, get with get_scores method (mysql, osuapi blabla)
			lock.acquire()
			b.setData(scoreData["beatmap_md5"], 0)
			lock.release()
		else:
			# If we have data, set data from dict
			b.setDataFromDict(scoreData)

		# Make sure the beatmap is ranked
		if b.rankedStatus != rankedStatuses.RANKED and b.rankedStatus != rankedStatuses.APPROVED and b.rankedStatus != rankedStatuses.QUALIFIED:
			#consoleHelper.printColored("[!] Beatmap {} is not ranked ().".format(s.fileMd5), bcolors.RED)
			return False

		# Calculate score pp
		s.calculatePP(b)

		# Update score pp
		scoreData["pp"] = s.pp
		return True

	class worker:
		def __init__(self, id, scores, lock):
			self.id = id
			self.scores = scores
			self.lock = lock
			self.perc = 0.00
			self.current = 1
			self.total = len(self.scores)
			self.done = False

		def doWork(self):
			if self.scores != None:
				for i in self.scores:
					recalcFromScoreData(i, self.lock)
					self.perc = (100*self.current)/self.total
					#print("{} is Working".format(self.id))
					#consoleHelper.printColored("[WORKER{}]\t{}/{}\t({:.2f}%)".format(self.id, c, tot, self.perc), bcolors.YELLOW)
					self.current+=1

				consoleHelper.printColored("[WORKER{}] PP calc for this worker finished. Saving results in db...".format(self.id), bcolors.PINK)
				for i in self.scores:
					self.lock.acquire()
					glob.db.execute("UPDATE scores SET pp = ? WHERE id = ?", [i["pp"], i["id"]])
					self.lock.release()
				self.done = True

	def massRecalc(scores):
		"""
		Recalc pp for scores in scores dictionary.

		scores -- dictionary returned from query. must contain id key with score id
		"""
		WORKERS = 32
		totalScores = len(scores)
		start = 0
		end = 0

		lock = threading.Lock()
		workers = []
		for i in range(0,WORKERS):
			start = end
			end = start+math.floor(len(scores)/WORKERS)

			consoleHelper.printColored("> Spawning worker {} ({}:{})".format(i, start, end), bcolors.PINK)
			workers.append(worker(i, scores[start:end], lock))
			t = threading.Thread(target=workers[i].doWork)
			t.start()

		while True:
			totalPerc = 0
			scoresDone = 0
			workersDone = 0
			for i in range(0,WORKERS):
				totalPerc += workers[i].perc
				scoresDone += workers[i].current
				if workers[i].done == True:
					workersDone += 1
			consoleHelper.printColored("> Progress {perc:.2f}% ({done}/{total}) [{donew}/{workers}]".format(perc=totalPerc/WORKERS, done=scoresDone, total=totalScores, donew=workersDone, workers=WORKERS), bcolors.GREEN)
			time.sleep(1)

			if workersDone == WORKERS:
				break


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
	glob.debug = generalHelper.stringToBool(glob.conf.config["server"]["debug"])
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
		print("> Recalculating pp for every score")
		scores = glob.db.fetchAll("SELECT * FROM scores LEFT JOIN beatmaps ON scores.beatmap_md5 = beatmaps.beatmap_md5 WHERE scores.play_mode = '0' AND scores.completed = '3' ORDER BY scores.id DESC;")
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
		#recalcFromScoreID(args.id)
		pass

	consoleHelper.printColored("Done!", bcolors.GREEN)
