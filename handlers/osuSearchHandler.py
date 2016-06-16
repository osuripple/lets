from constants import exceptions
from helpers import requestHelper
from helpers import userHelper
from helpers import osuapiHelper
import glob

# Exception tracking
import tornado.web
import tornado.gen
import sys
import traceback
from raven.contrib.tornado import SentryMixin

MODULE_NAME = "direct"
class handler(SentryMixin, requestHelper.asyncRequestHandler):
	"""
	Handler for /web/osu-search.php
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncGet(self):
		try:
			# Get request ip
			ip = self.getRequestIP()

			# Check arguments
			#if requestHelper.checkArguments(self.request.arguments, ["u", "h", "m", "r"]) == False:
			#	raise exceptions.invalidArgumentsException(MODULE_NAME)

			# Get arguments
			#username = self.get_argument("u")
			#password = self.get_argument("h")
			gameMode = self.get_argument("m")
			rankedStatus = self.get_argument("r")

			# Login check
			#userID = userHelper.getID(username)
			#if userID == 0:
			#	raise exceptions.loginFailedException(MODULE_NAME, username)
			#userHelper.checkLogin(userID, password, ip)

			# Default values for bloodcat query
			bcM = "0"
			bcS = "1,2,3,0"
			bcQ = ""
			bcPopular = False
			bcP = 1

			# Output string
			output = ""

			# Game Mode(s)
			if gameMode == "-1":
				# all modes
				bcM = "0,1,2,3"
			else:
				# specific mode
				bcM = gameMode

			# Ranked status
			# Bloodcat and osu! use different
			# ranked status ids for beatmap
			if rankedStatus == "0" or rankedStatus == "7":
				bcS = "1"
			elif rankedStatus == "3":
				bcS = "3"
			elif rankedStatus == "2":
				bcS = "2"
			elif rankedStatus == "5":
				bcS = "0"
			elif rankedStatus == "4":
				bcS = "1,2,3,0"

			# Search query
			# To search for Top rated, most played and newest beatmaps,
			# osu! sends a specific query to osu! direct search script.
			# Bloodcat uses a popular.php file instead to show all popular maps
			# If we have selected top rated/most played, we'll fetch popular.php's content
			# If we have selected newest, we'll fetch index.php content with no search query
			# Otherwise, we've searched for a specific map, so we pass the search query
			# to bloodcat
			if "q" in self.request.arguments:
				reqQ = self.get_argument("q")
				if reqQ == "Top Rated" or reqQ == "Most Played":
					bcPopular = True
				elif reqQ == "Newest":
					bcQ = ""
				else:
					bcQ = reqQ
			else:
				bcQ = ""

			# Page
			# Osu's first page is 0
			# Bloodcat's first page is 1
			if "p" in self.request.arguments:
				bcP = int(self.get_argument("p")) + 1

			# Replace spaces with +
			bcQ = bcQ.replace(" ", "+")

			# Build the URL with popular.php or normal bloodcat API
			if bcPopular == True:
				bcURL = "http://bloodcat.com/osu/popular.php?mod=json&m={}&p={}".format(bcM, bcP)
			else:
				bcURL = "http://bloodcat.com/osu/?mod=json&m={}&s={}&q={}&p={}".format(bcM, bcS, bcQ, bcP)

			# Get data from bloodcat API
			bcData = osuapiHelper.bloodcatRequest(bcURL)

			# Show 101 if we have >= 40 results (bloodcat maps per page)
			# or osu! won't load next pages
			if len(bcData) >= 40:
				output += str(101)
			else:
				output += str(len(bcData))

			# Separator
			output += "\n"

			# Add to output beatmap info for each song
			for i in bcData:
				output += osuapiHelper.bloodcatToDirect(i)+"\r\n"

			# Old memes
			output += "\r\n"

			# Return response
			self.write(output)
		except exceptions.invalidArgumentsException:
			pass
		except exceptions.loginFailedException:
			pass
		except:
			log.error("Unknown error in {}!\n```{}\n{}```".format(MODULE_NAME, sys.exc_info(), traceback.format_exc()))
			if glob.sentry:
				yield tornado.gen.Task(self.captureException, exc_info=True)
		#finally:
		#	self.finish()
