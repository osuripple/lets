import contextlib

import oppai

from common.constants import gameModes, mods
from common.log import logUtils as log
from constants import exceptions
from helpers import mapsHelper
from objects import glob

MODULE_NAME = "ez"

stats = {
	"latency": {
		gameModes.STD: {
			"classic": glob.stats["pp_calc_latency_seconds"].labels(game_mode="std", relax="0"),
			"relax": glob.stats["pp_calc_latency_seconds"].labels(game_mode="std", relax="1")
		},
		gameModes.TAIKO: {
			"classic": glob.stats["pp_calc_latency_seconds"].labels(game_mode="taiko", relax="0"),
			"relax": glob.stats["pp_calc_latency_seconds"].labels(game_mode="taiko", relax="1")
		}
	},
	"failures": {
		gameModes.STD: {
			"classic": glob.stats["pp_calc_failures"].labels(game_mode="std", relax="0"),
			"relax": glob.stats["pp_calc_failures"].labels(game_mode="std", relax="1")
		},
		gameModes.TAIKO: {
			"classic": glob.stats["pp_calc_failures"].labels(game_mode="taiko", relax="0"),
			"relax": glob.stats["pp_calc_failures"].labels(game_mode="taiko", relax="1")
		}
	}
}

class Ez:
	"""
	Std pp cacalculator, based on oppai-ng
	"""

	def __init__(self, beatmap_, score_=None, acc=None, mods_=None, tillerino=False, gameMode=gameModes.STD):
		"""
		Set oppai params.

		beatmap_ -- beatmap object
		score_ -- score object
		acc -- manual acc. Used in tillerino-like bot. You don't need this if you pass __score object
		mods_ -- manual mods. Used in tillerino-like bot. You don't need this if you pass __score object
		tillerino -- If True, self.pp will be a list with pp values for 100%, 99%, 98% and 95% acc. Optional.
		"""
		# Default values
		self.pp = None
		self.score = None
		self.acc = 0
		self.mods = mods.NOMOD
		self.combo = -1		# FC
		self.misses = 0
		self.stars = 0
		self.tillerino = tillerino

		# Beatmap object
		self.beatmap = beatmap_

		# If passed, set everything from score object
		if score_ is not None:
			self.score = score_
			self.acc = self.score.accuracy * 100
			self.mods = self.score.mods
			self.combo = self.score.maxCombo
			self.misses = self.score.cMiss
			self.gameMode = self.score.gameMode
		else:
			# Otherwise, set acc and mods from params (tillerino)
			self.acc = acc
			self.mods = mods_
			if gameMode is not None:
				self.gameMode = gameMode
			elif self.beatmap.starsStd > 0:
				self.gameMode = gameModes.STD
			elif self.beatmap.starsTaiko > 0:
				self.gameMode = gameModes.TAIKO
			else:
				self.gameMode = None

		# Calculate pp
		log.debug("oppai ~> Initialized oppai diffcalc")
		self.calculatePP()

	def _calculatePP(self):
		"""
		Calculate total pp value with oppai and return it

		return -- total pp
		"""
		# Set variables
		self.pp = None
		ez = None
		try:
			# Build .osu map file path
			mapFile = mapsHelper.cachedMapPath(self.beatmap.beatmapID)
			mapsHelper.cacheMap(mapFile, self.beatmap)

			# Use only mods supported by oppai
			modsFixed = self.mods & 5983

			# Check gamemode
			if self.gameMode not in (gameModes.STD, gameModes.TAIKO):
				raise exceptions.unsupportedGameModeException()

			ez = oppai.ezpp_new()

			if self.misses > 0:
				oppai.ezpp_set_nmiss(ez, self.misses)
			if self.combo >= 0:
				oppai.ezpp_set_combo(ez, self.combo)
			if self.gameMode == gameModes.TAIKO:
				oppai.ezpp_set_mode_override(ez, gameModes.TAIKO)
			if not self.tillerino:
				if self.acc > 0:
					oppai.ezpp_set_accuracy_percent(ez, self.acc)
			if self.mods > mods.NOMOD:
				oppai.ezpp_set_mods(ez, modsFixed)
			relax = (self.mods & mods.RELAX) > 0
			autopilot = (self.mods & mods.RELAX2) > 0
			if relax or autopilot:
				oppai.ezpp_set_relax_version(ez, 1)
				if relax:
					oppai.ezpp_set_relax(ez, 1)
				elif autopilot:
					oppai.ezpp_set_autopilot(ez, 1)

			if not self.tillerino:
				oppai.ezpp_dup(ez, mapFile)
				temp_pp = oppai.ezpp_pp(ez)
				self.stars = oppai.ezpp_stars(ez)
				if (self.gameMode == gameModes.TAIKO and self.beatmap.starsStd > 0 and temp_pp > 800) or \
					self.stars > 50:
					# Invalidate pp for bugged taiko converteds and bugged inf pp std maps
					self.pp = 0
				else:
					self.pp = temp_pp
			else:
				with open(mapFile, "r") as f:
					data = f.read()
				oppai.ezpp_data_dup(ez, data, len(data.encode()))
				pp_list = []
				self.stars = oppai.ezpp_stars(ez)
				oppai.ezpp_set_autocalc(ez, 1)
				for acc in (100, 99, 98, 95):
					oppai.ezpp_set_accuracy_percent(ez, acc)
					pp = oppai.ezpp_pp(ez)
					# If this is a broken converted, set all pp to 0 and break the loop
					if self.gameMode == gameModes.TAIKO and self.beatmap.starsStd > 0 and pp > 800:
						pp_list = [0, 0, 0, 0]
						break
					pp_list.append(pp)
				self.pp = pp_list
			log.debug("oppai ~> Calculated PP: {}, stars: {}".format(self.pp, self.stars))
		except exceptions.osuApiFailException:
			log.error("oppai ~> osu!api error!")
			self.pp = 0
		except exceptions.unsupportedGameModeException:
			log.error("oppai ~> Unsupported gamemode")
			self.pp = 0
		except Exception as e:
			log.error("oppai ~> Unhandled exception: {}".format(str(e)))
			self.pp = 0
			raise
		finally:
			if ez is not None:
				oppai.ezpp_free(ez)
			log.debug("oppai ~> Shutting down, pp = {}".format(self.pp))

	def calculatePP(self):
		latencyCtx = contextlib.suppress()
		excC = None
		if not self.tillerino and self.score.gameMode in (gameModes.STD, gameModes.TAIKO):
			latencyCtx = stats["latency"][self.score.gameMode]["classic" if not self.score.isRelax else "relax"].time()
			excC = stats["failures"][self.score.gameMode]["classic" if not self.score.isRelax else "relax"]
		with latencyCtx:
			try:
				return self._calculatePP()
			finally:
				if self.pp <= 0 and excC is not None:
					excC.inc()
