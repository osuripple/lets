from helpers import aeshelper
from helpers import userHelper
import score
import os
import glob
from constants import gameModes
from constants import exceptions
from helpers import requestHelper
from helpers import leaderboardHelper
import sys
import traceback
from helpers import logHelper as log
from helpers import scoreHelper
from helpers.exceptionsTracker import trackExceptions
import beatmap
import scoreboard
import collections

# Exception tracking
import tornado.web
import tornado.gen
from raven.contrib.tornado import SentryMixin

MODULE_NAME = "submit_modular"
class handler(SentryMixin, requestHelper.asyncRequestHandler):
	"""
	Handler for /web/osu-submit-modular.php
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	def asyncPost(self):
		try:
			# Resend the score in case of unhandled exceptions
			keepSending = True

			# Get request ip
			ip = self.getRequestIP()

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

			# Get bmk and bml (notepad hack check)
			if "bmk" in self.request.arguments and "bml" in self.request.arguments:
				bmk = self.get_argument("bmk")
				bml = self.get_argument("bml")
			else:
				bmk = None
				bml = None

			# Get right AES Key
			if "osuver" in self.request.arguments:
				aeskey = "osu!-scoreburgr---------{}".format(self.get_argument("osuver"))
			else:
				aeskey = "h89f2-890h2h89b34g-h80g134n90133"

			# Get score data
			log.debug("Decrypting score data...")
			scoreData = aeshelper.decryptRinjdael(aeskey, iv, scoreDataEnc, True).split(":")
			username = scoreData[1].strip()

			# Login and ban check
			userID = userHelper.getID(username)
			if userID == 0:
				raise exceptions.loginFailedException(MODULE_NAME, userID)
			#if userHelper.checkLogin(userID, password, ip) == False:
			#	raise exceptions.loginFailedException(MODULE_NAME, username)
			# Check active bancho session (NOTE: it searches only by userID, not ip)
			if userHelper.checkBanchoSession(userID) == False:
				# TODO: Ban (see except exceptions.noBanchoSessionException block)
				raise exceptions.noBanchoSessionException(MODULE_NAME, username, ip)
			if userHelper.isBanned(userID) == True:
				raise exceptions.userBannedException(MODULE_NAME, username)

			# Get restricted
			restricted = userHelper.isRestricted(userID)

			# Create score object and set its data
			log.info("{} has submitted a score on {}...".format(username, scoreData[0]))
			s = score.score()
			s.setDataFromScoreData(scoreData)

			# Calculate PP
			# NOTE: PP are std only
			if s.gameMode == gameModes.STD:
				s.calculatePP()

			# Restrict obvious cheaters
			if s.pp <= 700 and restricted == False:
				userHelper.restrict(userID)
				userHelper.appendNotes(userID, "-- Restricted due to too high pp gain ({}pp)".format(s.pp))
				log.warning("{} ({}) has been restricted due to too high pp gain ({}pp)".format(username, userID, s.pp), "cm")

			# Check notepad hack
			if bmk == None and bml == None:
				# No bmk and bml params passed, edited or super old client
				log.warning("{} ({}) most likely submitted a score from an edited client or a super old client".format(username, userID), "cm")
			elif bmk != bml and restricted == False:
				# bmk and bml passed and they are different, restrict the user
				userHelper.restrict(userID)
				userHelper.appendNotes(userID, "-- Restricted due to notepad hack")
				log.warning("{} ({}) has been restricted due to notepad hack".format(username, userID), "cm")

			# Save score in db
			s.saveScoreInDB()

			# Make sure process list has been passed
			if s.completed == 3 and "pl" not in self.request.arguments and restricted == False:
				userHelper.restrict(userID)
				userHelper.appendNotes(userID, "-- Restricted due to missing process list while submitting a score (most likely he used a score submitter)".format(s.pp))
				log.warning("{} ({}) has been restricted due to missing process list".format(username, userID), "cm")

			# Save replay
			if s.passed == True and s.completed == 3 and restricted == False:
				if "score" not in self.request.files:
					# Ban if no replay passed
					userHelper.restrict(userID)
					userHelper.appendNotes(userID, "-- Restricted due to missing replay while submitting a score (most likely he used a score submitter)".format(s.pp))
					log.warning("{} ({}) has been restricted due to replay not found on map {}".format(username, userID, s.fileMd5), "cm")
				else:
					# Otherwise, save the replay
					log.debug("Saving replay ({})...".format(s.scoreID))
					replay = self.request.files["score"][0]["body"]
					with open(".data/replays/replay_{}.osr".format(s.scoreID), "wb") as f:
						f.write(replay)

			# Make sure the replay has been saved (debug)
			if not os.path.isfile(".data/replays/replay_{}.osr".format(s.scoreID)) and s.completed == 3:
				log.error("Replay for score {} not saved!!".format(s.scoreID), "bunker")

			# Update beatmap playcount (and passcount)
			beatmap.incrementPlaycount(s.fileMd5, s.passed)

			# Get "before" stats for ranking panel (only if passed)
			if s.passed == True:
				# Get stats and rank
				oldUserData = glob.userStatsCache.get(userID, s.gameMode)
				oldRank = leaderboardHelper.getUserRank(userID, s.gameMode)

				# Beatmap info needed for personal best (if not in cacge)
				# song playcount and passcount
				beatmapInfo = beatmap.beatmap()
				beatmapInfo.setDataFromDB(s.fileMd5)

				# Try to get oldPersonalBestRank from cache
				oldPersonalBestRank = glob.personalBestCache.get(userID, s.fileMd5)
				if oldPersonalBestRank == 0:
					# oldPersonalBestRank not found in cache, get it from db
					oldScoreboard = scoreboard.scoreboard(username, s.gameMode, beatmapInfo, False)
					oldScoreboard.setPersonalBest()
					oldPersonalBestRank = oldScoreboard.personalBestRank if oldScoreboard.personalBestRank > 0 else 0
			else:
				# We need to do this or it throws an exception when building ranking panel
				beatmapInfo = None

			# Always update users stats (total/ranked score, playcount, level, acc and pp)
			# even if not passed
			log.debug("Updating {}'s stats...".format(username))
			userHelper.updateStats(userID, s)

			# Get "after" stats for ranking panel
			# and to determine if we should update the leaderboard
			# (only if we passed that song)
			if s.passed == True:
				# Get new stats
				newUserData = userHelper.getUserStats(userID, s.gameMode)
				glob.userStatsCache.update(userID, s.gameMode, newUserData)

				# Use pp/score as "total" based on game mode
				if s.gameMode == gameModes.STD:
					criteria = "pp"
				else:
					criteria = "rankedScore"

				# Update leaderboard if score/pp has changed
				if s.completed == 3 and newUserData[criteria] != oldUserData[criteria]:
					leaderboardHelper.update(userID, newUserData[criteria], s.gameMode)

			# TODO: Update total hits and max combo
			# Update latest activity
			userHelper.updateLatestActivity(userID)

			# IP botnet
			userHelper.botnet(userID, ip)

			# Score submission and stats update done
			log.debug("Score submission and user stats update done!")

			# Score has been submitted, do not retry sending the score if
			# there are exceptions while building the ranking panel
			keepSending = False

			# Output ranking panel only if we passed the song
			# and we got valid beatmap info from db
			if beatmapInfo != None or beatmapInfo != False and s.passed == True:
				log.debug("Started building ranking panel")

				# Get personal best after submitting the score
				newScoreboard = scoreboard.scoreboard(username, s.gameMode, beatmapInfo, False)
				newScoreboard.setPersonalBest()

				# Get rank info (current rank, pp/score to next rank, user who is 1 rank above us)
				rankInfo = leaderboardHelper.getRankInfo(userID, s.gameMode)

				# Output dictionary
				output = collections.OrderedDict()
				output["beatmapId"] = beatmapInfo.beatmapID
				output["beatmapSetId"] = beatmapInfo.beatmapSetID
				output["beatmapPlaycount"] = beatmapInfo.playcount
				output["beatmapPasscount"] = beatmapInfo.passcount
				#output["approvedDate"] = "2015-07-09 23:20:14\n"
				output["approvedDate"] = "\n"
				output["chartId"] = "overall"
				output["chartName"] = "Overall Ranking"
				output["chartEndDate"] = ""
				output["beatmapRankingBefore"] = oldPersonalBestRank
				output["beatmapRankingAfter"] = newScoreboard.personalBestRank
				output["rankedScoreBefore"] = oldUserData["rankedScore"]
				output["rankedScoreAfter"] = newUserData["rankedScore"]
				output["totalScoreBefore"] = oldUserData["totalScore"]
				output["totalScoreAfter"] = newUserData["totalScore"]
				output["playCountBefore"] = newUserData["playcount"]
				output["accuracyBefore"] = float(oldUserData["accuracy"])/100
				output["accuracyAfter"] = float(newUserData["accuracy"])/100
				output["rankBefore"] = oldRank
				output["rankAfter"] = rankInfo["currentRank"]
				output["toNextRank"] = rankInfo["difference"]
				output["toNextRankUser"] = rankInfo["nextUsername"]
				output["achievements"] = ""
				try:
					# std only
					if s.gameMode != 0:
						raise

					# Get best score if
					bestID = int(glob.db.fetch("SELECT id FROM scores WHERE userid = %s AND play_mode = %s AND completed = 3 ORDER BY pp DESC LIMIT 1", [userID, s.gameMode])["id"])
					if bestID == s.scoreID:
						# Dat pp achievement
						output["achievements-new"] = "all-secret-jackpot+Here come dat PP+Oh shit waddup"
					else:
						raise
				except:
					# No achievement
					output["achievements-new"] = ""
				output["onlineScoreId"] = s.scoreID

				# Build final string
				msg = ""
				for line, val in output.items():
					msg += "{}:{}".format(line, val)
					if val != "\n":
						if (len(output) - 1) != list(output.keys()).index(line):
							msg += "|"
						else:
							msg += "\n"

				# Some debug messages
				log.debug("Generated output for online ranking screen!")
				log.debug(msg)

				# Write message to client
				self.write(msg)
			else:
				# No ranking panel, send just "ok"
				self.write("ok")
		except exceptions.invalidArgumentsException:
			pass
		except exceptions.loginFailedException:
			self.write("error: pass")
		except exceptions.userBannedException:
			self.write("error: ban")
		except exceptions.noBanchoSessionException:
			# We don't have an active bancho session.
			# Don't ban the user but tell the client to send the score again.
			# Once we are sure that this error doesn't get triggered when it
			# shouldn't (eg: bancho restart), we'll ban users that submit
			# scores without an active bancho session.
			# We only log through schiavo atm (see exceptions.py).
			#self.set_status(408)
			self.write("error: pass")
		except:
			# Try except block to avoid more errors
			try:
				log.error("Unknown error in {}!\n```{}\n{}```".format(MODULE_NAME, sys.exc_info(), traceback.format_exc()))
				if glob.sentry:
					yield tornado.gen.Task(self.captureException, exc_info=True)
			except:
				pass

			# Every other exception returns a 408 error (timeout)
			# This avoids lost scores due to score server crash
			# because the client will send the score again after some time.
			if keepSending == True:
				self.set_status(408)
