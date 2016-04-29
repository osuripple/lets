import requests
import json
from lets import glob
from helpers import generalHelper
from constants import bcolors
from helpers import consoleHelper
import glob

def osuApiRequest(request, params):
	"""
	Send a request to osu!api.

	request -- request type, string (es: get_beatmaps)
	params -- GET parameters, without api key or trailing ?/& (es: h=a5b99395a42bd55bc5eb1d2411cbdf8b&limit=10)
	return -- dictionary with json response if success, None if failed or empty response.
	"""
	# Make sure osuapi is enabled
	if generalHelper.stringToBool(glob.conf.config["osuapi"]["enable"]) == False:
		print("osuapi is disabled")
		return None

	# Api request
	try:
		finalURL = "{}/api/{}?k={}&{}".format(glob.conf.config["osuapi"]["apiurl"], request, glob.conf.config["osuapi"]["apikey"], params)
		#print("Sending request to osu!api: {}".format(finalURL))
		resp = requests.get(finalURL).text
		#print("Got response: {}".format(resp))
		data = json.loads(resp)
		if len(data) >= 1:
			return data[0]
		else:
			return None
	except:
		consoleHelper.printColored("[!] Error while contacting osu!api", bcolors.RED)
		return None

def getOsuFile(beatmapID):
	"""
	Send a request to osu! servers to download a .osu file
	Used to update beatmaps

	beatmapID -- ID of beatmap to download
	return -- .osu file content if success, None if failed
	"""
	try:
		# Make sure osuapi is enabled
		if generalHelper.stringToBool(glob.conf.config["osuapi"]["enable"]) == False:
			print("osuapi is disabled")
			return None

		# TODO: proxy
		URL = "{}/osu/{}".format(glob.conf.config["osuapi"]["apiurl"], beatmapID)
		consoleHelper.printColored(str(URL), bcolors.BLUE)
		response = request.get(URL).text
		return data
	except:
		consoleHelper.printColored("[!] Error while downloading .osu file", bcolors.RED)
		return None
