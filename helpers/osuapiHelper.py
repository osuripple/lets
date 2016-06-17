import requests
import json
from lets import glob
from helpers import generalHelper
import glob
from urllib.parse import quote
from helpers import logHelper as log
import sys
import traceback

def osuApiRequest(request, params):
	"""
	Send a request to osu!api.

	request -- request type, string (es: get_beatmaps)
	params -- GET parameters, without api key or trailing ?/& (es: h=a5b99395a42bd55bc5eb1d2411cbdf8b&limit=10)
	return -- dictionary with json response if success, None if failed or empty response.
	"""
	# Make sure osuapi is enabled
	if generalHelper.stringToBool(glob.conf.config["osuapi"]["enable"]) == False:
		log.warning("osu!api is disabled")
		return None

	# Api request
	resp = None
	try:
		finalURL = "{}/api/{}?k={}&{}".format(glob.conf.config["osuapi"]["apiurl"], request, glob.conf.config["osuapi"]["apikey"], params)
		resp = requests.get(finalURL, timeout=5).text
		data = json.loads(resp)
		if len(data) >= 1:
			resp = data[0]
		else:
			resp = None
	finally:
		return resp

def getOsuFileFromName(fileName):
	"""
	Send a request to osu! servers to download a .osu file from file name
	Used to update beatmaps

	fileName -- .osu file name to download
	return -- .osu file content if success, None if failed
	"""
	response = None
	try:
		# Make sure osuapi is enabled
		if generalHelper.stringToBool(glob.conf.config["osuapi"]["enable"]) == False:
			print("osuapi is disabled")
			return None

		URL = "{}/web/maps/{}".format(glob.conf.config["osuapi"]["apiurl"], quote(fileName))
		response = requests.get(URL, timeout=20).text
	finally:
		return response

def getOsuFileFromID(beatmapID):
	"""
	Send a request to osu! servers to download a .osu file from beatmap ID
	Used to get .osu files for oppai

	beatmapID -- ID of beatmap (not beatmapset) to download
	return -- .osu file content if success, None if failed
	"""
	response = None
	try:
		# Make sure osuapi is enabled
		if generalHelper.stringToBool(glob.conf.config["osuapi"]["enable"]) == False:
			print("osuapi is disabled")
			return None

		URL = "{}/osu/{}".format(glob.conf.config["osuapi"]["apiurl"], beatmapID)
		response = requests.get(URL, timeout=20).text
	finally:
		return response

def bloodcatRequest(URL):
	response = None
	try:
		response = requests.get(URL, timeout=10).text
		response = json.loads(response)
	finally:
		return response

def bloodcatToDirect(data, np = False):
	s = ""
	if np == True:
		s = "{id}.osz|{artist}|{title}|{creator}|{status}|10.00|{synced}|{id}|{id}|0|0|0|".format(**data)
	else:
		s = "{id}.osz|{artist}|{title}|{creator}|{status}|10.00|{synced}|{id}|".format(**data)
		s += "{}|0|0|0||".format(data["beatmaps"][0]["id"])
		for i in data["beatmaps"]:
			s += "{name}@{mode},".format(**i)
		s = s.strip(",")
		s += '|'

	return s
