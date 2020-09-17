import json

import tornado.gen
import tornado.web

from objects import beatmap
from common.constants import gameModes
from common.log import logUtils as log
from common.web import requestsManager
from constants import exceptions
from helpers import osuapiHelper
from pp import ez, cicciobello, wifipiano3
from common.sentry import sentry


class handler(requestsManager.asyncRequestHandler):
	"""
	Handler for /api/v1/pp
	"""
	MODULE_NAME = "api/pp"

	@tornado.web.asynchronous
	@tornado.gen.engine
	@sentry.captureTornado
	def asyncGet(self):
		statusCode = 400
		data = {"message": "unknown error"}
		try:
			# Check arguments
			if not requestsManager.checkArguments(self.request.arguments, ["b"]):
				raise exceptions.invalidArgumentsException(self.MODULE_NAME)

			# Get beatmap ID and make sure it's a valid number
			beatmapID = self.get_argument("b")
			if not beatmapID.isdigit():
				raise exceptions.invalidArgumentsException(self.MODULE_NAME)

			# Get mods
			if "m" in self.request.arguments:
				modsEnum = self.get_argument("m")
				if not modsEnum.isdigit():
					raise exceptions.invalidArgumentsException(self.MODULE_NAME)
				modsEnum = int(modsEnum)
			else:
				modsEnum = 0

			# Get game mode
			if "g" in self.request.arguments:
				gameMode = self.get_argument("g")
				if not gameMode.isdigit():
					raise exceptions.invalidArgumentsException(self.MODULE_NAME)
				gameMode = int(gameMode)
			else:
				gameMode = 0

			# Get acc
			if "a" in self.request.arguments:
				accuracy = self.get_argument("a")
				try:
					accuracy = float(accuracy)
				except ValueError:
					raise exceptions.invalidArgumentsException(self.MODULE_NAME)
			else:
				accuracy = None

			# Print message
			log.info("Requested pp for beatmap {}".format(beatmapID))

			# Get beatmap md5 from osuapi
			# TODO: Move this to beatmap object
			osuapiData = osuapiHelper.osuApiRequest("get_beatmaps", "b={}".format(beatmapID))
			if osuapiData is None or "file_md5" not in osuapiData or "beatmapset_id" not in osuapiData:
				raise exceptions.invalidBeatmapException(self.MODULE_NAME)
			beatmapMd5 = osuapiData["file_md5"]
			beatmapSetID = osuapiData["beatmapset_id"]

			# Create beatmap object
			bmap = beatmap.beatmap(beatmapMd5, beatmapSetID)

			# Check beatmap length
			if bmap.hitLength > 900:
				raise exceptions.beatmapTooLongException(self.MODULE_NAME)

			if gameMode == gameModes.STD and bmap.starsStd == 0:
				# Mode Specific beatmap, auto detect game mode
				if bmap.starsTaiko > 0:
					gameMode = gameModes.TAIKO
				if bmap.starsCtb > 0:
					gameMode = gameModes.CTB
				if bmap.starsMania > 0:
					gameMode = gameModes.MANIA

			# Calculate pp
			if gameMode in (gameModes.STD, gameModes.TAIKO):
				# osu!standard and osu!taiko
				oppai = ez.Ez(bmap, mods_=modsEnum, tillerino=accuracy is None, acc=accuracy, gameMode=gameMode)
				bmap.starsStd = oppai.stars
				returnPP = oppai.pp
			elif gameMode == gameModes.CTB:
				# osu!catch
				ciccio = cicciobello.Cicciobello(
					bmap,
					mods_=modsEnum,
					tillerino=accuracy is None,
					accuracy=accuracy
				)
				bmap.starsStd = ciccio.stars
				returnPP = ciccio.pp
			else:
				raise exceptions.unsupportedGameModeException()

			# Data to return
			data = {
				"song_name": bmap.songName,
				"pp": [x for x in returnPP] if type(returnPP) is list else returnPP,
				"game_mode": gameMode,
				"length": bmap.hitLength,
				"stars": bmap.starsStd,
				"ar": bmap.AR,
				"bpm": bmap.bpm,
			}

			# Set status code and message
			statusCode = 200
			data["message"] = "ok"
		except exceptions.invalidArgumentsException:
			# Set error and message
			statusCode = 400
			data["message"] = "missing required arguments"
		except exceptions.invalidBeatmapException:
			statusCode = 400
			data["message"] = "beatmap not found"
		except exceptions.beatmapTooLongException:
			statusCode = 400
			data["message"] = "requested beatmap is too long"
		except exceptions.unsupportedGameModeException:
			statusCode = 400
			data["message"] = "Unsupported gamemode"
		finally:
			# Add status code to data
			data["status"] = statusCode

			# Debug output
			log.debug(str(data))

			# Send response
			self.write(json.dumps(data))
			self.set_header("Content-Type", "application/json")
			self.set_status(statusCode)


def calculatePPFromAcc(ppcalc, acc):
	ppcalc.acc = acc
	ppcalc.calculatePP()
	return ppcalc.pp
