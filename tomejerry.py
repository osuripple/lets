import argparse
import math
import os
import threading
import time

import progressbar

from objects import beatmap
from objects import score
from common.constants import bcolors
from common.db import dbConnector
from common.ripple import userUtils
from constants import rankedStatuses
from helpers import config
from helpers import consoleHelper
from common import generalUtils
from objects import glob

# constants
MAX_WORKERS = 32
MODULE_NAME = "rippoppai"
UNIX = True if os.name == "posix" else False

# Global stuff
args = None

if __name__ == "__main__":
	# Verbose
	glob.debug = False

	def recalcFromScoreData(scoreData):
		"""
		Recalculate pp value for a score.
		Does every check, output and queries needed.

		score -- score+beatmap dictionary (returned from db with JOIN) of score to recalc
		return -- calculated pp value or None
		"""

		# Create score object and set its data
		s = score.score()
		s.setDataFromDict(scoreData)
		if s.scoreID == 0:
			# Make sure the score exists
			if glob.debug:
				consoleHelper.printColored("[!] No score with id {}".format(scoreData["id"]), bcolors.RED)

		# Create beatmap object
		b = beatmap.beatmap()

		# Check if we have data for this song
		if scoreData["song_name"] is None or args.apirefresh == True:
			# If we don't have song data in scoreData, get with get_scores method (mysql, osuapi blabla)
			b.setData(scoreData["beatmap_md5"], 0)
		else:
			# If we have data, set data from dict
			b.setDataFromDict(scoreData)

		# Make sure the beatmap is ranked
		if b.rankedStatus < rankedStatuses.RANKED:
			if glob.debug:
				consoleHelper.printColored("[!] Beatmap {} is not ranked ().".format(s.fileMd5), bcolors.RED)
			# Don't calculate pp if the beatmap is not ranked
			return False

		# Calculate score pp
		s.calculatePP(b)

		# Update score pp in dictionary
		scoreData["pp"] = s.pp
		return True

	class worker:
		"""
		rippoppai recalculator worker
		"""
		def __init__(self, _id, scores):
			"""
			Instantiate a worker

			id -- worker numeric id
			scores -- list of scores+beatmaps dictionaries to recalc
			"""
			self.id = _id
			self.scores = scores
			self.perc = 0.00
			self.current = 0
			self.total = len(self.scores)
			self.done = False

		def doWork(self):
			"""
			Worker's work
			Basically, calculate pp for scores inside self.scores
			"""

			# Make sure scores have been passed
			if self.scores is not None:
					for i in self.scores:
						try:
							# Loop through all scores
							# Recalculate pp
							recalcFromScoreData(i)

							# Calculate percentage
							self.perc = (100*self.current)/self.total

							# Update recalculated count
							self.current+=1
						except Exception as e:
							consoleHelper.printColored("LA SIGNORA ANNA È MORTA! ({})".format(e), bcolors.YELLOW)

					# Recalculation finished, save new pp values in db
					consoleHelper.printColored("[WORKER{}] PP calc for this worker finished. Saving results in db...".format(self.id), bcolors.PINK)
					try:
						for i in self.scores:
							# Loop through all scores and update pp in db
							glob.db.execute("UPDATE scores SET pp = %s WHERE id = %s", [i["pp"], i["id"]])
					except:
						consoleHelper.printColored("Errore query stampa piede intensifies", bcolors.RED)

			# This worker has finished his work
			self.done = True

	def massRecalc(scores, workersNum = 0):
		"""
		Recalc pp for scores in scores dictionary.

		scores -- dictionary returned from query. must contain id key with score id
		workersNum -- number of workers. If 0, will spawn 1 worker every 200 scores up to MAX_WORKERS
		"""
		# Get total scores number
		totalScores = len(scores)

		# Calculate number of workers if needed
		if workersNum == 0:
			workersNum = min(math.ceil(totalScores/200), MAX_WORKERS)

		# Start from the first score
		end = 0

		# Create workers list
		workers = []

		# Spawn necessary workers
		for i in range(0,workersNum):
			# Set this worker's scores range
			start = end
			end = start+math.floor(len(scores)/workersNum)
			consoleHelper.printColored("> Spawning worker {} ({}:{})".format(i, start, end), bcolors.PINK)

			# Append a worker object to workers list, passing scores to recalc
			workers.append(worker(i, scores[start:end]))

			# Create this worker's thread and start it
			t = threading.Thread(target=workers[i].doWork)
			t.start()

		# Infinite output loop
		with progressbar.ProgressBar(widgets=[
			"\033[92m",
			"Progress:", progressbar.FormatLabel(" %(value)s/%(max)s "),
			progressbar.Bar(marker='#', left='[', right=']', fill='.'),
			"\033[93m ",
			progressbar.Percentage(),
			" (", progressbar.ETA(), ") ",
			"\033[0m",
		], max_value=totalScores, redirect_stdout=True) as bar:
			while True:
				# Variables needed to calculate percentage
				totalPerc = 0
				scoresDone = 0
				workersDone = 0

				# Loop through all workers
				for i in range(0,workersNum):
					# Get percentage, calculated scores number and done status
					totalPerc += workers[i].perc
					scoresDone += workers[i].current
					if workers[i].done:
						workersDone += 1

				# Output global information
				#consoleHelper.printColored("> Progress {perc:.2f}% ({done}/{total}) [{donew}/{workers}]".format(perc=totalPerc/workersNum, done=scoresDone, total=totalScores, donew=workersDone, workers=workersNum), bcolors.YELLOW)
				bar.update(scoresDone)

				# Exit from the loop if every worker has finished its work
				if workersDone == workersNum:
					break

				# Repeat after 0.1 seconds
				time.sleep(0.1)

	# CLI stuff
	__author__ = "Nyo"
	parser = argparse.ArgumentParser(description="pp recalc tool for ripple")
	parser.add_argument('-r','--recalc', help="recalculate pp for every score", required=False, action='store_true')
	parser.add_argument('-z','--zero', help="calculate pp for 0 pp scores", required=False, action='store_true')
	parser.add_argument('-i','--id', help="calculate pp for score with this id", required=False)
	parser.add_argument('-m','--mods', help="calculate pp for scores with this mod (mod id)", required=False)
	parser.add_argument('-g','--gamemode', help="calculate pp for scores with this gamemode (std:0, taiko: 1, ctb:2, mania:3)", required=False)
	parser.add_argument('-u','--userid', help="calculate pp for scores played by a specific user (userID)", required=False)
	parser.add_argument('-b', '--beatmapid', help="calculate pp for scores played by a specific beatmap (beatmapID)", required=False)
	parser.add_argument('-n','--username', help="calculate pp for scores played by a specific user (username)", required=False)
	parser.add_argument('-l', '--loved', help="calculate pp for scores played on non-frozen loved beatmaps", required=False, action='store_true')
	parser.add_argument('-a','--apirefresh', help="always fetch beatmap data from osu!api", required=False, action='store_true')
	parser.add_argument('-w','--workers', help="force number of workers", required=False)
	parser.add_argument('-v','--verbose', help="run ripp in verbose/debug mode", required=False, action='store_true')
	args = parser.parse_args()

	# Platform
	print("Running under {}".format("UNIX" if UNIX == True else "WIN32"))

	# Load config
	consoleHelper.printNoNl("> Reading config file... ")
	glob.conf = config.config("config.ini")
	glob.debug = generalUtils.stringToBool(glob.conf.config["server"]["debug"])
	consoleHelper.printDone()

	# Get workers from arguments if set
	workers = 0
	if args.workers is not None:
		workers = int(args.workers)

	# Connect to MySQL
	try:
		consoleHelper.printNoNl("> Connecting to MySQL db")
		glob.db = dbConnector.db(
			glob.conf.config["db"]["host"],
			glob.conf.config["db"]["username"],
			glob.conf.config["db"]["password"],
			glob.conf.config["db"]["database"],
			max(workers, MAX_WORKERS)
		)
		consoleHelper.printNoNl(" ")
		consoleHelper.printDone()
	except:
		consoleHelper.printError()
		consoleHelper.printColored("[!] Error while connection to database. Please check your config.ini and run the server again", bcolors.RED)
		raise

	# Set verbose
	glob.debug = args.verbose

	# Operations
	if args.zero:
		# 0pp recalc
		print("> Recalculating pp for zero-pp scores")
		scores = glob.db.fetchAll("SELECT * FROM scores LEFT JOIN beatmaps ON scores.beatmap_md5 = beatmaps.beatmap_md5 WHERE scores.completed = 3 AND scores.pp = 0 ORDER BY scores.id DESC;")
		massRecalc(scores, workers)
	elif args.recalc:
		# Full recalc
		print("> Recalculating pp for every score")
		scores = glob.db.fetchAll("SELECT * FROM scores LEFT JOIN beatmaps ON scores.beatmap_md5 = beatmaps.beatmap_md5 WHERE scores.completed = 3 ORDER BY scores.id DESC;")
		massRecalc(scores, workers)
	elif args.mods is not None:
		# Mods recalc
		print("> Recalculating pp for scores with mods {}".format(args.mods))
		allScores = glob.db.fetchAll("SELECT * FROM scores LEFT JOIN beatmaps ON scores.beatmap_md5 = beatmaps.beatmap_md5 WHERE scores.completed = 3 ORDER BY scores.id DESC;")
		scores = []
		for i in allScores:
			if i["mods"] & int(args.mods) > 0:
				#consoleHelper.printColored("> PP for score {} will be recalculated (mods: {})".format(i["id"], i["mods"]), bcolors.GREEN)
				scores.append(i)
		massRecalc(scores, workers)
	elif args.id is not None:
		# Score ID recalc
		print("> Recalculating pp for score ID {}".format(args.id))
		scores = glob.db.fetchAll("SELECT * FROM scores LEFT JOIN beatmaps ON scores.beatmap_md5 = beatmaps.beatmap_md5 WHERE scores.id = %s;", [args.id])
		massRecalc(scores, workers)
	elif args.gamemode is not None:
		# game mode recalc
		print("> Recalculating pp for gamemode {}".format(args.gamemode))
		scores = glob.db.fetchAll("SELECT * FROM scores LEFT JOIN beatmaps ON scores.beatmap_md5 = beatmaps.beatmap_md5 WHERE scores.play_mode = %s AND scores.completed = 3", [args.gamemode])
		massRecalc(scores, workers)
	elif args.userid is not None:
		# User ID recalc
		print("> Recalculating pp for user {}".format(args.userid))
		scores = glob.db.fetchAll("SELECT * FROM scores LEFT JOIN beatmaps ON scores.beatmap_md5 = beatmaps.beatmap_md5 WHERE scores.completed = 3 AND scores.userid = %s;", [args.userid])
		massRecalc(scores, workers)
	elif args.username is not None:
		# Username recalc
		print("> Recalculating pp for user {}".format(args.username))
		uid = userUtils.getID(args.username)
		if uid != 0:
			scores = glob.db.fetchAll("SELECT * FROM scores LEFT JOIN beatmaps ON scores.beatmap_md5 = beatmaps.beatmap_md5 WHERE scores.completed = 3 AND scores.userid = %s;", [uid])
			massRecalc(scores, workers)
		# TODO: error message xd
	elif args.loved:
		# Loved recalc
		print("> Recalculating pp for un-frozen loved beatmaps")
		scores = glob.db.fetchAll("SELECT * FROM scores LEFT JOIN beatmaps ON scores.beatmap_md5 = beatmaps.beatmap_md5 WHERE beatmaps.ranked = 5 AND scores.completed = 3 ORDER BY scores.id DESC;")
		massRecalc(scores, workers)
	elif args.beatmapid is not None:
		# beatmap id recalc
		print("> Recalculating pp for beatmap id {}".format(args.beatmapid))
		scores = glob.db.fetchAll("SELECT * FROM scores LEFT JOIN beatmaps ON scores.beatmap_md5 = beatmaps.beatmap_md5 WHERE scores.completed = 3 AND beatmaps.beatmap_id = %s;", [args.beatmapid])
		massRecalc(scores, workers)

	# The endTM
	consoleHelper.printColored("Done!", bcolors.GREEN)
