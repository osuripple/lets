import collections
import json
import os
import sys
import traceback
from urllib.parse import urlencode

import requests
import tornado.gen
import tornado.web

from objects import beatmap
from objects import score
from objects import scoreboard
from common.constants import gameModes
from common.log import logUtils as log
from common.ripple import userUtils
from common.web import requestsManager
from constants import exceptions
from constants import rankedStatuses
from helpers import aeshelper
from helpers import leaderboardHelper
from objects import glob
from common.sentry import sentry

MODULE_NAME = "submit_modular"
class handler(requestsManager.asyncRequestHandler):
	"""
	Handler for /web/osu-submit-modular.php
	"""
	@tornado.web.asynchronous
	@tornado.gen.engine
	#@sentry.captureTornado
	def asyncPost(self):
		try:
			# Resend the score in case of unhandled exceptions
			keepSending = True

			# Get request ip
			ip = self.getRequestIP()

			# Print arguments
			if glob.debug:
				requestsManager.printArguments(self)

			# Check arguments
			if not requestsManager.checkArguments(self.request.arguments, ["score", "iv", "pass"]):
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
			userID = userUtils.getID(username)
			# User exists check
			if userID == 0:
				raise exceptions.loginFailedException(MODULE_NAME, userID)
			# Bancho session/username-pass combo check
			if not userUtils.checkLogin(userID, password, ip):
				raise exceptions.loginFailedException(MODULE_NAME, username)
			# Generic bancho session check
			#if not userUtils.checkBanchoSession(userID):
				# TODO: Ban (see except exceptions.noBanchoSessionException block)
			#	raise exceptions.noBanchoSessionException(MODULE_NAME, username, ip)
			# Ban check
			if userUtils.isBanned(userID):
				raise exceptions.userBannedException(MODULE_NAME, username)
			# Data length check
			if len(scoreData) < 16:
				raise exceptions.invalidArgumentsException(MODULE_NAME)

			# Get restricted
			restricted = userUtils.isRestricted(userID)

			# Create score object and set its data
			log.info("{} has submitted a score on {}...".format(username, scoreData[0]))
			s = score.score()
			s.setDataFromScoreData(scoreData)

			# Get beatmap info
			beatmapInfo = beatmap.beatmap()
			beatmapInfo.setDataFromDB(s.fileMd5)

			# Make sure the beatmap is submitted and updated
			if beatmapInfo.rankedStatus == rankedStatuses.NOT_SUBMITTED or beatmapInfo.rankedStatus == rankedStatuses.NEED_UPDATE or beatmapInfo.rankedStatus == rankedStatuses.UNKNOWN:
				log.debug("Beatmap is not submitted/outdated/unknown. Score submission aborted.")
				return

			# Calculate PP
			# NOTE: PP are std and mania only
			if s.gameMode == gameModes.STD or s.gameMode == gameModes.MANIA:
				s.calculatePP()

			# Restrict obvious cheaters
			if (s.pp >= 700 and s.gameMode == gameModes.STD) and restricted == False:
				userUtils.restrict(userID)
				userUtils.appendNotes(userID, "-- Restricted due to too high pp gain ({}pp)".format(s.pp))
				log.warning("**{}** ({}) has been restricted due to too high pp gain **({}pp)**".format(username, userID, s.pp), "cm")

			# Check notepad hack
			if bmk is None and bml is None:
				# No bmk and bml params passed, edited or super old client
				#log.warning("{} ({}) most likely submitted a score from an edited client or a super old client".format(username, userID), "cm")
				pass
			elif bmk != bml and restricted == False:
				# bmk and bml passed and they are different, restrict the user
				userUtils.restrict(userID)
				userUtils.appendNotes(userID, "-- Restricted due to notepad hack")
				log.warning("**{}** ({}) has been restricted due to notepad hack".format(username, userID), "cm")
				return

			# Save score in db
			s.saveScoreInDB()

			# Client anti-cheat flags
			'''ignoreFlags = 4
			if glob.debug == True:
				# ignore multiple client flags if we are in debug mode
				ignoreFlags |= 8
			haxFlags = (len(scoreData[17])-len(scoreData[17].strip())) & ~ignoreFlags
			if haxFlags != 0 and restricted == False:
				userHelper.restrict(userID)
				userHelper.appendNotes(userID, "-- Restricted due to clientside anti cheat flag ({}) (cheated score id: {})".format(haxFlags, s.scoreID))
				log.warning("**{}** ({}) has been restricted due clientside anti cheat flag **({})**".format(username, userID, haxFlags), "cm")'''

			# Make sure process list has been passed
			if s.completed == 3 and "pl" not in self.request.arguments and restricted == False:
				userUtils.restrict(userID)
				userUtils.appendNotes(userID, "-- Restricted due to missing process list while submitting a score (most likely he used a score submitter)")
				log.warning("**{}** ({}) has been restricted due to missing process list".format(username, userID), "cm")

			# Save replay
			if s.passed == True and s.completed == 3:
				if "score" not in self.request.files:
					if not restricted:
						# Ban if no replay passed
						userUtils.restrict(userID)
						userUtils.appendNotes(userID, "-- Restricted due to missing replay while submitting a score (most likely he used a score submitter)")
						log.warning("**{}** ({}) has been restricted due to replay not found on map {}".format(username, userID, s.fileMd5), "cm")
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
			if s.passed:
				# Get stats and rank
				oldUserData = glob.userStatsCache.get(userID, s.gameMode)
				oldRank = leaderboardHelper.getUserRank(userID, s.gameMode)

				# Try to get oldPersonalBestRank from cache
				oldPersonalBestRank = glob.personalBestCache.get(userID, s.fileMd5)
				if oldPersonalBestRank == 0:
					# oldPersonalBestRank not found in cache, get it from db
					oldScoreboard = scoreboard.scoreboard(username, s.gameMode, beatmapInfo, False)
					oldScoreboard.setPersonalBest()
					oldPersonalBestRank = oldScoreboard.personalBestRank if oldScoreboard.personalBestRank > 0 else 0

			# Always update users stats (total/ranked score, playcount, level, acc and pp)
			# even if not passed
			log.debug("Updating {}'s stats...".format(username))
			userUtils.updateStats(userID, s)

			# Get "after" stats for ranking panel
			# and to determine if we should update the leaderboard
			# (only if we passed that song)
			if s.passed:
				# Get new stats
				newUserData = userUtils.getUserStats(userID, s.gameMode)
				glob.userStatsCache.update(userID, s.gameMode, newUserData)

				# Use pp/score as "total" based on game mode
				if s.gameMode == gameModes.STD or s.gameMode == gameModes.MANIA:
					criteria = "pp"
				else:
					criteria = "rankedScore"

				# Update leaderboard if score/pp has changed
				if s.completed == 3 and newUserData[criteria] != oldUserData[criteria]:
					leaderboardHelper.update(userID, newUserData[criteria], s.gameMode)

			# TODO: Update total hits and max combo
			# Update latest activity
			userUtils.updateLatestActivity(userID)

			# IP log
			userUtils.IPLog(userID, ip)

			# Score submission and stats update done
			log.debug("Score submission and user stats update done!")

			# Score has been submitted, do not retry sending the score if
			# there are exceptions while building the ranking panel
			keepSending = False

			# Output ranking panel only if we passed the song
			# and we got valid beatmap info from db
			if beatmapInfo is not None and beatmapInfo != False and s.passed == True:
				log.debug("Started building ranking panel")

				# Trigger bancho stats cache update
				glob.redis.publish("peppy:update_cached_stats", userID)

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
						raise Exception

					# Get best score if
					bestID = int(glob.db.fetch("SELECT id FROM scores WHERE userid = %s AND play_mode = %s AND completed = 3 ORDER BY pp DESC LIMIT 1", [userID, s.gameMode])["id"])
					if bestID == s.scoreID:
						# Dat pp achievement
						output["achievements-new"] = "all-secret-jackpot+Here come dat PP+Oh shit waddup"
					else:
						raise Exception
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


				# send message to #announce if we're rank #1
				if newScoreboard.personalBestRank == 1 and s.completed == 3 and restricted == False:
					annmsg = "[https://ripple.moe/?u={} {}] achieved rank #1 on [https://osu.ppy.sh/b/{} {}] ({})".format(userID, username, beatmapInfo.beatmapID, beatmapInfo.songName, gameModes.getGamemodeFull(s.gameMode))
					params = urlencode({"k": glob.conf.config["server"]["apikey"], "to": "#announce", "msg": annmsg})
					requests.get("{}/api/v1/fokabotMessage?{}".format(glob.conf.config["server"]["banchourl"], params))

				# Write message to client
				self.write(msg)
			else:
				# No ranking panel, send just "ok"
				self.write("ok")

			# Send username change request to bancho if needed
			# (key is deleted bancho-side)
			newUsername = glob.redis.get("ripple:change_username_pending:{}".format(userID))
			if newUsername is not None:
				log.debug("Sending username change request for user {} to Bancho".format(userID))
				glob.redis.publish("peppy:change_username", json.dumps({
					"userID": userID,
					"newUsername": newUsername.decode("utf-8")
				}))

			# Datadog stats
			glob.dog.increment(glob.DATADOG_PREFIX+".submitted_scores")
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
			self.set_status(408)
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
			if keepSending:
				self.set_status(408)
