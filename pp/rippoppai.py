"""
oppai interface for ripple 2 / LETS
"""

import os

import pyoppai

from common import generalUtils
from common.log import logUtils as log
from common.constants import bcolors
from constants import exceptions
from helpers import consoleHelper
from helpers import osuapiHelper
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
	if UNIX:
		return command
	return command.replace("/", "\\")


class OppaiError(Exception):
	def __init__(self, error):
		self.error = error


class oppai:
	"""
	Oppai cacalculator
	"""

	# Folder where oppai is placed
	OPPAI_FOLDER = ".data/oppai"
	BUFSIZE = 2000000
	# __slots__ = ["pp", "score", "acc", "mods", "combo", "misses", "stars", "beatmap", "map"]

	def __init__(self, __beatmap, __score = None, acc = 0, mods = 0, tillerino = False):
		"""
		Set oppai params.

		__beatmap -- beatmap object
		__score -- score object
		acc -- manual acc. Used in tillerino-like bot. You don't need this if you pass __score object
		mods -- manual mods. Used in tillerino-like bot. You don't need this if you pass __score object
		tillerino -- If True, self.pp will be a list with pp values for 100%, 99%, 98% and 95% acc. Optional.
		"""
		# Default values
		self.pp = None
		self.score = None
		self.acc = 0
		self.mods = 0
		self.combo = 0
		self.misses = 0
		self.stars = 0
		self.tillerino = tillerino

		# Beatmap object
		self.beatmap = __beatmap
		self.map = "{}.osu".format(self.beatmap.beatmapID)

		# If passed, set everything from score object
		if __score is not None:
			self.score = __score
			self.acc = self.score.accuracy*100
			self.mods = self.score.mods
			self.combo = self.score.maxCombo
			self.misses = self.score.cMiss
		else:
			# Otherwise, set acc and mods from params (tillerino)
			self.acc = acc
			self.mods = mods

		# Oppai stuff
		self._oppai_ctx = pyoppai.new_ctx()
		self._oppai_beatmap = pyoppai.new_beatmap(self._oppai_ctx)
		self._oppai_buffer = pyoppai.new_buffer(self.BUFSIZE)
		self._oppai_diffcalc_ctx = None

		# Calculate pp
		log.debug("oppai ~> Initialized oppai diffcalc")
		self.calculatePP()

	def checkOppaiErrors(self):
		log.debug("oppai ~> Checking oppai errors...")
		err = pyoppai.err(self._oppai_ctx)
		if err:
			log.error(str(err))
			raise OppaiError(err)
		log.debug("oppai ~> No errors!")

	def calculatePP(self):
		"""
		Calculate total pp value with oppai and return it

		return -- total pp
		"""
		# Set variables
		self.pp = None
		try:
			# Build .osu map file path
			mapFile = "{path}/maps/{map}".format(path=self.OPPAI_FOLDER, map=self.map)
			log.debug("oppai ~> Map file: {}".format(mapFile))

			try:
				# Check if we have to download the .osu file
				download = False
				if not os.path.isfile(mapFile):
					# .osu file doesn't exist. We must download it
					if glob.debug:
						consoleHelper.printColored("[!] {} doesn't exist".format(mapFile), bcolors.YELLOW)
					download = True
				else:
					# File exists, check md5
					if generalUtils.fileMd5(mapFile) != self.beatmap.fileMD5:
						# MD5 don't match, redownload .osu file
						if glob.debug:
							consoleHelper.printColored("[!] Beatmaps md5 don't match", bcolors.YELLOW)
						download = True

				# Download .osu file if needed
				if download:
					log.debug("oppai ~> Downloading {} osu file".format(self.beatmap.beatmapID))

					# Get .osu file from osu servers
					fileContent = osuapiHelper.getOsuFileFromID(self.beatmap.beatmapID)

					# Make sure osu servers returned something
					if fileContent is None:
						raise exceptions.osuApiFailException(MODULE_NAME)

					# Delete old .osu file if it exists
					if os.path.isfile(mapFile):
						os.remove(mapFile)

					# Save .osu file
					with open(mapFile, "wb+") as f:
						f.write(fileContent.encode("utf-8"))
				else:
					# Map file is already in folder
					log.debug("oppai ~> Beatmap found in cache!")
			except exceptions.osuApiFailException:
				log.error("oppai ~> osu!api error!")
				pass

			# Parse beatmap
			log.debug("oppai ~> About to parse beatmap")
			pyoppai.parse(
				mapFile,
				self._oppai_beatmap,
				self._oppai_buffer,
				self.BUFSIZE,
				False,
				self.OPPAI_FOLDER # /oppai_cache
			)
			self.checkOppaiErrors()
			log.debug("oppai ~> Beatmap parsed with no errors")

			# Create diffcalc context and calculate difficulty
			log.debug("oppai ~> About to calculate difficulty")

			# Use only mods supported by oppai
			modsFixed = self.mods & 5979
			if modsFixed > 0:
				pyoppai.apply_mods(self._oppai_beatmap, modsFixed)
			self._oppai_diffcalc_ctx = pyoppai.new_d_calc_ctx(self._oppai_ctx)
			diff_stars, diff_aim, diff_speed, _, _, _, _ = pyoppai.d_calc(self._oppai_diffcalc_ctx, self._oppai_beatmap)
			self.checkOppaiErrors()
			log.debug("oppai ~> Difficulty calculated with no errors. {}*, {} aim, {} speed".format(diff_stars, diff_aim, diff_speed))

			# Calculate pp
			log.debug("oppai ~> About to calculate PP")
			if not self.tillerino:
				_, total_pp, aim_pp, speed_pp, acc_pp =  pyoppai.pp_calc_acc(self._oppai_ctx, diff_aim, diff_speed, self._oppai_beatmap,
													                   self.acc if self.acc > 0 else 100,
													                   modsFixed,
													                   self.combo if self.combo > 0 else 0xFFFF,
													                   self.misses)
				self.checkOppaiErrors()
				log.debug("oppai ~> PP Calculated with no errors. {}pp, {} aim pp, {} speed pp, {} acc pp".format(
					total_pp, aim_pp, speed_pp, acc_pp
				))
				self.pp = total_pp
			else:
				pp_list = []
				for acc in [100, 99, 98, 95]:
					log.debug("oppai ~> Calculating PP with acc {}%".format(acc))
					_, total_pp, aim_pp, speed_pp, acc_pp = pyoppai.pp_calc_acc(self._oppai_ctx, diff_aim, diff_speed,
					                                                      self._oppai_beatmap, acc, modsFixed)
					self.checkOppaiErrors()
					pp_list.append(total_pp)
					log.debug("oppai ~> PP Calculated with no errors. {}pp, {} aim pp, {} speed pp, {} acc pp".format(
						total_pp, aim_pp, speed_pp, acc_pp
					))
					self.pp = pp_list
			self.stars = diff_stars

			log.debug("oppai ~> Calculated PP: {}".format(self.pp))
		except OppaiError:
			log.error("oppai ~> pyoppai error!")
			self.pp = 0
		except Exception as e:
			log.error("oppai ~> Unhandled exception: {}".format(str(e)))
			raise e
		finally:
			log.debug("oppai ~> Shutting down and returning {}pp".format(self.pp))
			return self.pp
