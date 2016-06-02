import tornado.web
from helpers import consoleHelper
from constants import bcolors
from helpers import aeshelper
from helpers import userHelper
from helpers import discordBotHelper
import score
import os
import glob
from constants import gameModes
from constants import exceptions
from helpers import requestHelper
from helpers import leaderboardHelper
import sys
import traceback

#if os.path.isfile("rippoppai.py"):
#	import rippoppai

MODULE_NAME = "submit_modular"
class handler(requestHelper.asyncRequestHandler):
	"""
	Handler for /web/osu-submit-modular.php
	"""
	def asyncPost(self):
		try:
			# Print arguments
			if glob.debug == True:
				requestHelper.printArguments(self)

			# Check arguments
			if requestHelper.checkArguments(self.request.arguments, ["score", "iv", "pass"]) == False:
				raise exceptions.invalidArgumentsException(MODULE_NAME)

			# TODO: Maintenance check

			# Get parameters and IP
			scoreDataEnc = self.get_argument("score")
			iv = self.get_argument("iv")
			password = self.get_argument("pass")
			ip = self.getRequestIP()

			# Get right AES Key
			if "osuver" in self.request.arguments:
				aeskey = "osu!-scoreburgr---------{}".format(self.get_argument("osuver"))
			else:
				aeskey = "h89f2-890h2h89b34g-h80g134n90133"

			# Get score data
			consoleHelper.printColored("----", bcolors.YELLOW)
			consoleHelper.printSubmitModularMessage("Decrypting score data...")
			scoreData = aeshelper.decryptRinjdael(aeskey, iv, scoreDataEnc, True).split(":")
			username = scoreData[1].strip()

			# Login and ban check
			userID = userHelper.getID(username)
			if userID == 0:
				raise exceptions.loginFailedException(MODULE_NAME, userID)
			if userHelper.checkLogin(userID, password) == False:
				raise exceptions.loginFailedException(MODULE_NAME, username)
			if userHelper.getAllowed(userID) == 0:
				raise exceptions.userBannedException(MODULE_NAME, username)
			# Create score object and set its data
			consoleHelper.printSubmitModularMessage("Saving {}'s score on {}...".format(username, scoreData[0]))
			s = score.score()
			s.setDataFromScoreData(scoreData)

			# Calculate PP
			# NOTE: PP are std only
			if glob.pp == True and s.gameMode == gameModes.STD:
				s.calculatePP()

			# Ban obvious cheaters
			if s.pp >= 700:
				userHelper.setAllowed(userID, 0)
				discordBotHelper.sendConfidential("{} ({}) has been banned due to too high pp gain ({}pp)".format(username, userID, s.pp))

			# Save score in db
			s.saveScoreInDB()

			# Make sure process list has been passed
			if s.completed == 3 and "pl" not in self.request.arguments:
				userHelper.setAllowed(userID, 0)
				discordBotHelper.sendConfidential("{} ({}) has been banned due to missing process list".format(username, userID))

			# Save replay
			if s.passed == True and s.completed == 3:
				if "score" not in self.request.files:
					# Ban if no replay passed
					userHelper.setAllowed(userID, 0)
					discordBotHelper.sendConfidential("{} ({}) has been banned due to replay not found on map {}".format(username, userID, s.fileMd5))
				else:
					# Otherwise, save the replay
					consoleHelper.printSubmitModularMessage("Saving replay ({})...".format(s.scoreID))
					replay = self.request.files["score"][0]["body"]
					with open(".data/replays/replay_{}.osr".format(s.scoreID), "wb") as f:
						f.write(replay)

			# Make sure the replay has been saved (debug)
			if not os.path.isfile(".data/replays/replay_{}.osr".format(s.scoreID)) and s.completed == 3:
				discordBotHelper.sendConfidential("Replay for score {} not saved!!".format(s.scoreID), True)

			# Update users stats (total/ranked score, playcount, level and acc)
			consoleHelper.printSubmitModularMessage("Updating {}'s stats...".format(username))
			userHelper.updateStats(userID, s)

			# Update leaderboard
			if glob.pp == True and s.gameMode == gameModes.STD:
				newScore = userHelper.getPP(userID, s.gameMode)
			else:
				newScore = userHelper.getRankedScore(userID, s.gameMode)

			# Update leaderboard
			leaderboardHelper.update(userID, newScore, s.gameMode)

			# TODO: Update total hits and max combo
			# Update latest activity
			userHelper.updateLatestActivity(userID)

			# IP botnet
			userHelper.botnet(userID, ip)

			# Done!
			consoleHelper.printSubmitModularMessage("Done!")
			self.write("ok")
		except exceptions.invalidArgumentsException:
			pass
		except exceptions.loginFailedException:
			self.write("error: pass")
		except exceptions.userBannedException:
			self.write("error: ban")
		except:
			# Try except block to avoid more errors
			try:
				msg = "Unknown error in score submission!\n```{}\n{}```".format(sys.exc_info(), traceback.format_exc())
				consoleHelper.printColored("[!] {}".format(msg), bcolors.RED)
				discordBotHelper.sendConfidential(msg, True)
			except:
				pass

			# Every other exception returns a 408 error (timeout)
			# This avoids lost scores due to score server crash
			# because the client will send the score again after some time.
			self.send_error(408)
		finally:
			self.finish()
