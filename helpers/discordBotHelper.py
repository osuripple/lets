import requests
from lets import glob
from helpers import generalHelper
from urllib.parse import urlencode

def sendDiscordMessage(channel, message, alertDev = False):
	"""
	Send a message to a discord server.
	This is used with ripple's schiavobot.

	channel -- bunk, staff or general
	message -- message to send
	alertDev -- if True, hl developers group
	"""
	if generalHelper.stringToBool(glob.conf.config["discord"]["enable"]) == True:
		for _ in range(0,20):
			try:
				finalMsg = message if alertDev == False else "{} - {}".format(glob.conf.config["discord"]["devgroup"], message)
				requests.get("{}/{}?{}".format(glob.conf.config["discord"]["boturl"], channel, urlencode({ "message": finalMsg })))
				break
			except:
				continue


def sendConfidential(message, alertDev = False):
	"""
	Send a message to #bunker

	message -- message to send
	"""
	sendDiscordMessage("bunk", message, alertDev)


def sendStaff(message):
	"""
	Send a message to #staff

	message -- message to send
	"""
	sendDiscordMessage("staff", message)


def sendGeneral(message):
	"""
	Send a message to #general

	message -- message to send
	"""
	sendDiscordMessage("general", message)
