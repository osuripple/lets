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
			if userHelper.checkLogin(userID, password, ip) == False:
				raise exceptions.loginFailedException(MODULE_NAME, username)
			if userHelper.getAllowed(userID) == 0:
				raise exceptions.userBannedException(MODULE_NAME, username)

			# Check active bancho session (NOTE: it searches only by userID, not ip)
			if userHelper.checkBanchoSession(userID) == False:
				# TODO: Ban (see except exceptions.noBanchoSessionException block)
				raise exceptions.noBanchoSessionException(MODULE_NAME, username, ip)

			# Create score object and set its data
			log.info("{} has submitted a score on {}...".format(username, scoreData[0]))
			s = score.score()
			s.setDataFromScoreData(scoreData)

			beatmapInfo = beatmap.beatmap()
			beatmapInfo.setDataFromDB(s.fileMd5)

			scores = scoreboard.scoreboard(username, s.gameMode, beatmapInfo, setScores = True)
			userData = userHelper.getUserData(userID)
			mode = scoreHelper.readableGameMode(s.gameMode)
			userRank = leaderboardHelper.getUserRank(userID, s.gameMode)

			# Calculate PP
			# NOTE: PP are std only
			if s.gameMode == gameModes.STD:
				s.calculatePP()

			# Ban obvious cheaters
			if s.pp >= 700:
				userHelper.setAllowed(userID, 0)
				log.warning("{} ({}) has been banned due to too high pp gain ({}pp)".format(username, userID, s.pp), True)

			# Save score in db
			s.saveScoreInDB()

			# Make sure process list has been passed
			if s.completed == 3 and "pl" not in self.request.arguments:
				userHelper.setAllowed(userID, 0)
				log.warning("{} ({}) has been banned due to missing process list".format(username, userID), True)

			# Save replay
			if s.passed == True and s.completed == 3:
				if "score" not in self.request.files:
					# Ban if no replay passed
					userHelper.setAllowed(userID, 0)
					log.warning("{} ({}) has been banned due to replay not found on map {}".format(username, userID, s.fileMd5), True)
				else:
					# Otherwise, save the replay
					log.debug("Saving replay ({})...".format(s.scoreID))
					replay = self.request.files["score"][0]["body"]
					with open(".data/replays/replay_{}.osr".format(s.scoreID), "wb") as f:
						f.write(replay)

			# Make sure the replay has been saved (debug)
			if not os.path.isfile(".data/replays/replay_{}.osr".format(s.scoreID)) and s.completed == 3:
				log.error("Replay for score {} not saved!!".format(s.scoreID), True)

			# Update users stats (total/ranked score, playcount, level and acc)
			log.debug("Updating {}'s stats...".format(username))
			userHelper.updateStats(userID, s)

			# Update leaderboard
			if s.gameMode == gameModes.STD:
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
			log.debug("Done!")
			if beatmapInfo != None or beatmapInfo != False:
				data = collections.defaultdict(lambda: 0)
				newScore = scoreboard.scoreboard(username, s.gameMode, beatmapInfo, setScores = True)
				newData = userHelper.getUserData(userID)
				playcount = glob.db.fetch("SELECT COUNT(id) AS count FROM scores WHERE beatmap_md5 = %s", [s.fileMd5])
				if playcount:
					data["playcount"] = playcount["count"]

				if userData:
					data["totalScoreBefore"] = userData["total_score_" + mode]
					data["playCountBefore"] = userData["playcount_" + mode]
					data["accuracyBefore"] = userData["avg_accuracy_" + mode]/100
					data["rankBefore"] = userRank["position"]
				if newData:
					data["totalScoreAfter"] = data["totalScoreBefore"] + s.score if beatmapInfo.rankedStatus > 0 else data["totalScoreBefore"]
					data["accuracyAfter"] = newData["avg_accuracy_" + mode]/100
					rankAfter = leaderboardHelper.getUserRank(userID, s.gameMode)
					data["rankAfter"] = rankAfter["position"]

				data["rankedScoreBefore"] = userData["ranked_score_" + mode]
				data["rankedScoreAfter"] = newData["ranked_score_" + mode]
				modeColumn = "pp_" + mode
				rankInfo = glob.db.fetch("SELECT {col}, username FROM users_stats WHERE {col} > %s ORDER BY {col} LIMIT 1".format(col=modeColumn), [data["rankedScoreAfter"]])
				if rankInfo:
					data["toNextRank"] = rankInfo[modeColumn]
					data["toNextRank"] -= newData['pp_' + mode]
					data["toNextRankUser"] = rankInfo["username"]

				data["beatmapRankingBefore"] = scores.personalBestRank if scores.personalBestRank > 0 else 0

				output = collections.OrderedDict()
				output["beatmapId"] = beatmapInfo.beatmapID
				output["beatmapSetId"] = beatmapInfo.beatmapSetID
				output["beatmapPlaycount"] = data["playcount"]
				output["beatmapPasscount"] = data["playcount"]
				output["approvedDate"] = "\n"
				output["chartId"] = "overall"
				output["chartName"] = "Overall Ranking"
				output["chartEndDate"] = ""
				output["beatmapRankingBefore"] = data["beatmapRankingBefore"]
				output["beatmapRankingAfter"] = newScore.personalBestRank
				output["rankedScoreBefore"] = data["rankedScoreBefore"]
				output["rankedScoreAfter"] = data["rankedScoreAfter"]
				output["totalScoreBefore"] = data["totalScoreBefore"]
				output["totalScoreAfter"] = data["totalScoreAfter"]
				output["playCountBefore"] = data["playCountBefore"]
				output["accuracyBefore"] = data["accuracyBefore"]
				output["accuracyAfter"] = data["accuracyAfter"]
				output["rankBefore"] = data["rankBefore"]
				output["rankAfter"] = data["rankAfter"]
				output["toNextRank"] = data["toNextRank"]
				output["toNextRankUser"] = data.get("toNextRankUser", "")
				output["achievements"] = ""
				output["onlineScoreId"] = s.scoreID

				msg = ""
				for line, val in output.items():
					msg += "{}:{}".format(line, val)
					if val != "\n":
						if (len(output) - 1) != list(output.keys()).index(line):
							msg += "|"
						else:
							msg += "\n"
				log.debug("Generated output for online ranking screen!")
				self.write(msg)
			else:
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
			self.set_status(408)
		#finally:
		#	self.finish()
