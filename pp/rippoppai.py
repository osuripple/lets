"""
oppai interface for ripple 2 / LETS
"""

import os
import subprocess

from common.constants import bcolors
from constants import exceptions
from helpers import consoleHelper
from common import generalUtils
from helpers import osuapiHelper
from helpers import scoreHelper
from objects import glob

# constants
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
	"""
	Oppai calculator
	"""
	# Folder where oppai is placed
	OPPAI_FOLDER = "../oppai"

	def __init__(self, __beatmap, __score = None, acc = 0, mods = 0, tillerino = False, stars = False):
		"""
		Set oppai params.

		__beatmap -- beatmap object
		__score -- score object
		acc -- manual acc. Used in tillerino-like bot. You don't need this if you pass __score object
		mods -- manual mods. Used in tillerino-like bot. You don't need this if you pass __score object
		tillerino -- If True, self.pp will be a list with pp values for 100%, 99%, 98% and 95% acc. Optional.
		stars -- If True, self.stars will be the star difficulty for the map (including mods)
		"""
		# Default values
		self.pp = 0
		self.score = None
		self.acc = 0
		self.mods = 0
		self.combo = 0
		self.misses = 0
		self.stars = 0

		# Beatmap object
		self.beatmap = __beatmap
		self.map = "{}.osu".format(self.beatmap.beatmapID)

		# If passed, set everything from score object
		if __score != None:
			self.score = __score
			self.acc = self.score.accuracy*100
			self.mods = self.score.mods
			self.combo = self.score.maxCombo
			self.misses = self.score.cMiss
		else:
			# Otherwise, set acc and mods from params (tillerino)
			self.acc = acc
			self.mods = mods

		# Calculate pp
		self.getPP(tillerino, stars)

	def getPP(self, tillerino = False, stars = False):
		"""
		Calculate total pp value with oppai and return it

		return -- total pp
		"""
		# Set variables
		command = None
		output = None
		self.pp = 0
		try:
			# Build .osu map file path
			mapFile = "{path}/maps/{map}".format(path=self.OPPAI_FOLDER, map=self.map)

			try:
				# Check if we have to download the .osu file
				download = False
				if not os.path.isfile(mapFile):
					# .osu file doesn't exist. We must download it
					if glob.debug == True:
						consoleHelper.printColored("[!] {} doesn't exist".format(mapFile), bcolors.YELLOW)
					download = True
				else:
					# File exists, check md5
					if generalUtils.fileMd5(mapFile) != self.beatmap.fileMD5:
						# MD5 don't match, redownload .osu file
						if glob.debug == True:
							consoleHelper.printColored("[!] Beatmaps md5 don't match".format(mapFile), bcolors.YELLOW)
						download = True

				# Download .osu file if needed
				if download == True:
					if glob.debug == True:
						consoleHelper.printRippoppaiMessage("Downloading {} from osu! servers...".format(self.beatmap.beatmapID))

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
					if glob.debug == True:
						consoleHelper.printRippoppaiMessage("Found beatmap file {}".format(mapFile))
			except exceptions.osuApiFailException:
				pass

			# Base command
			command = fixPath("{path}/oppai {mapFile}".format(path=self.OPPAI_FOLDER, mapFile=mapFile))

			# Use only mods supported by oppai.
			modsFixed = self.mods & 5979

			# Add params if needed
			if self.acc > 0:
				command += " {acc:.2f}%".format(acc=self.acc)
			if self.mods > 0:
				command += " +{mods}".format(mods=scoreHelper.readableMods(modsFixed))
			if self.combo > 0:
				command += " {combo}x".format(combo=self.combo)
			if self.misses > 0:
				command += " {misses}xm".format(misses=self.misses)
			if tillerino == True:
				command += " tillerino"
			if stars == True:
				command += " stars"

			# Debug output
			if glob.debug == True:
				consoleHelper.printRippoppaiMessage("Executing {}".format(command))

			# oppai output
			process = subprocess.run(command, shell=True, stdout=subprocess.PIPE)
			output = process.stdout.decode("utf-8")

			# Get standard or tillerino output
			sep = "\n" if UNIX else "\r\n"
			if output == ['']:
				# This happens if mode not supported or something
				self.pp = 0
				self.stars = None
				return self.pp

			output = output.split(sep)

			# get rid of pesky warnings!!!
			try:
				float(output[0])
			except ValueError:
				del output[0]

			if tillerino == True:
				# Get tillerino output (multiple lines)
				if stars == True:
					self.pp = output[:-2]
					self.stars = float(output[-2])
				else:
					self.pp = output.split(sep)[:-1]	# -1 because there's an empty line at the end
			else:
				# Get standard output (:l to remove (/r)/n at the end)
				l = -1 if UNIX else -2
				if stars == True:
					self.pp = float(output[len(output)-2][:l-1])
				else:
					self.pp = float(output[len(output)-2][:l])

			# Debug output
			if glob.debug == True:
				consoleHelper.printRippoppaiMessage("Calculated pp: {}".format(self.pp))
		finally:
			return self.pp
