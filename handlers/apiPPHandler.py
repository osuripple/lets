import json
from helpers import requestHelper
from constants import exceptions
import beatmap
from helpers import osuapiHelper
from helpers import consoleHelper
import rippoppai
import glob
import traceback
import sys

MODULE_NAME = "api/pp"
class handler(requestHelper.asyncRequestHandler):
	"""
	Handler for /api/v1/pp
	"""
	def asyncGet(self):
		statusCode = 400
		data = {"message": "unknown error"}
		try:
			# Check arguments
			if requestHelper.checkArguments(self.request.arguments, ["b"]) == False:
				raise exceptions.invalidArgumentsException(MODULE_NAME)

			# Get beatmap ID and make sure it's a valid number
			beatmapID = self.get_argument("b")
			if not beatmapID.isdigit():
				raise exceptions.invalidArgumentsException(MODULE_NAME)

			# Get mods
			if "m" in self.request.arguments:
				modsEnum = self.get_argument("m")
				if not modsEnum.isdigit():
					raise exceptions.invalidArgumentsException(MODULE_NAME)
				modsEnum = int(modsEnum)
			else:
				modsEnum = 0

			# Get acc
			if "a" in self.request.arguments:
				accuracy = self.get_argument("a")
				try:
					accuracy = float(accuracy)
				except ValueError:
					raise exceptions.invalidArgumentsException(MODULE_NAME)
			else:
				accuracy = -1.0

			# Print message
			consoleHelper.printApiMessage(MODULE_NAME, "Requested pp for beatmap {}".format(beatmapID))

			# Get beatmap md5 from osuapi
			# TODO: Move this to beatmap object
			osuapiData = osuapiHelper.osuApiRequest("get_beatmaps", "b={}".format(beatmapID))
			if "file_md5" not in osuapiData or "beatmapset_id" not in osuapiData:
				raise exceptions.invalidBeatmapException(MODULE_NAME)
			beatmapMd5 = osuapiData["file_md5"]
			beatmapSetID = osuapiData["beatmapset_id"]

			# Create beatmap object
			bmap = beatmap.beatmap(beatmapMd5, beatmapSetID)

			# Check beatmap length
			if bmap.hitLength > 900:
				raise exceptions.beatmapTooLongException(MODULE_NAME)

			returnPP = []
			if accuracy < 0 and modsEnum == 0:
				# Generic acc
				# Get cached pp values
				cachedPP = bmap.getCachedTillerinoPP()
				if cachedPP != [0,0,0,0]:
					consoleHelper.printApiMessage(MODULE_NAME, "Got cached pp.")
					returnPP = cachedPP
				else:
					consoleHelper.printApiMessage(MODULE_NAME, "Cached pp not found. Calculating pp with oppai...")
					# Cached pp not found, calculate them
					oppai = rippoppai.oppai(bmap, mods=modsEnum, tillerino=True)
					returnPP = oppai.pp

					# Cache values in DB
					consoleHelper.printApiMessage(MODULE_NAME, "Saving cached pp...")
					bmap.saveCachedTillerinoPP(returnPP)
			else:
				# Specific accuracy, calculate
				# Create oppai instance
				consoleHelper.printApiMessage(MODULE_NAME, "Specific request ({}%/{}). Calculating pp with oppai...".format(accuracy, modsEnum))
				oppai = rippoppai.oppai(bmap, mods=modsEnum, tillerino=True)
				if accuracy > 0:
					returnPP.append(calculatePPFromAcc(oppai, accuracy))
				else:
					returnPP = oppai.pp

			# Data to return
			data = {
				"song_name": bmap.songName,
				"pp": returnPP,
				"length": bmap.hitLength,
				"stars": bmap.stars,
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
		finally:
			# Add status code to data
			data["status"] = statusCode

			# Debug output
			if glob.debug == True:
				print(str(data))

			# Send response
			self.clear()
			self.set_status(statusCode)
			self.finish(json.dumps(data))

def calculatePPFromAcc(ppcalc, acc):
	ppcalc.acc = acc
	ppcalc.getPP()
	return ppcalc.pp
