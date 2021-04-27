import base64
import collections
import io
import json
import os
import sys
import threading
import traceback

import requests
import tornado.gen
import tornado.web
from timeout_decorator import timeout

import secret.achievements.utils
from common.constants import gameModes
from common.constants import mods
from common.log import logUtils as log
from common.ripple import userUtils, fokabot, bancho, scoreUtils
from common.sentry import sentry
from common.web import requestsManager
from constants import exceptions, autoLast, scoreOverwrite
from constants import rankedStatuses
from constants.exceptions import ppCalcException
from helpers import aeshelper
from helpers import s3
from helpers import replayHelper
from helpers import leaderboardHelper
from helpers.generalHelper import zingonify
from objects import beatmap
from objects import glob
from objects import score
from objects import scoreboard
from objects.charts import BeatmapChart, OverallChart
from secret import butterCake

class handler(requestsManager.asyncRequestHandler):
	"""
	Handler for /web/osu-submit-modular.php
	"""
	MODULE_NAME = "submit_modular"

	@tornado.web.asynchronous
	@tornado.gen.engine
	#@sentry.captureTornado
	def asyncPost(self):
		newCharts = self.request.uri == "/web/osu-submit-modular-selector.php"
		try:
			# Resend the score in case of unhandled exceptions
			keepSending = True

			# Get request ip
			ip = self.getRequestIP()

			# Print arguments
			if glob.conf["DEBUG"]:
				requestsManager.printArguments(self)

			# Check arguments
			if not requestsManager.checkArguments(self.request.arguments, ["score", "iv", "pass"]):
				raise exceptions.invalidArgumentsException(self.MODULE_NAME)

			# TODO: Maintenance check

			# Get parameters and IP
			scoreDataEnc = self.get_argument("score")
			iv = self.get_argument("iv")
			password = self.get_argument("pass")
			ip = self.getRequestIP()
			quit_ = self.get_argument("x", "0") == "1"
			try:
				failTime = max(0, int(self.get_argument("ft", 0)))
			except ValueError:
				raise exceptions.invalidArgumentsException(self.MODULE_NAME)
			failed = not quit_ and failTime > 0

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
			scoreData = aeshelper.decryptRinjdael(aeskey, iv, scoreDataEnc, True).split(":")
			log.debug(scoreData)
			if len(scoreData) < 16 or len(scoreData[0]) != 32:
				return
			username = scoreData[1].strip()

			# Login and ban check
			userID = userUtils.getID(username)
			# User exists check
			if userID == 0:
				raise exceptions.loginFailedException(self.MODULE_NAME, userID)

			# Score submission lock check
			lock_key = "lets:score_submission_lock:{}:{}:{}".format(userID, scoreData[0], int(scoreData[9]))
			if glob.redis.get(lock_key) is not None:
				# The same score score is being submitted and it's taking a lot
				log.warning("Score submission blocked because there's a submission lock in place ({})".format(lock_key))
				return

			# Set score submission lock
			log.debug("Setting score submission lock {}".format(lock_key))
			glob.redis.set(lock_key, "1", 120)

			# Bancho session/username-pass combo check
			if not userUtils.checkLogin(userID, password, ip):
				raise exceptions.loginFailedException(self.MODULE_NAME, username)
			# 2FA Check
			if userUtils.check2FA(userID, ip):
				raise exceptions.need2FAException(self.MODULE_NAME, userID, ip)
			# Generic bancho session check
			#if not userUtils.checkBanchoSession(userID):
				# TODO: Ban (see except exceptions.noBanchoSessionException block)
			#	raise exceptions.noBanchoSessionException(self.MODULE_NAME, username, ip)
			# Ban check
			if userUtils.isBanned(userID):
				raise exceptions.userBannedException(self.MODULE_NAME, username)
			# Data length check
			if len(scoreData) < 16:
				raise exceptions.invalidArgumentsException(self.MODULE_NAME)

			# Get restricted
			restricted = userUtils.isRestricted(userID)

			# Create score object and set its data
			log.info("{} has submitted a score on {}...".format(username, scoreData[0]))
			s = score.score()
			s.setDataFromScoreData(scoreData, quit_=quit_, failed=failed)

			# Set score stuff missing in score data
			s.playerUserID = userID

			# Get beatmap info
			beatmapInfo = beatmap.beatmap()
			beatmapInfo.setDataFromDB(s.fileMd5)

			# Make sure the beatmap is submitted and updated
			if beatmapInfo.rankedStatus in (
				rankedStatuses.NOT_SUBMITTED, rankedStatuses.NEED_UPDATE, rankedStatuses.UNKNOWN
			):
				log.debug("Beatmap is not submitted/outdated/unknown. Score submission aborted.")
				return

			# Set play time and full play time
			s.fullPlayTime = beatmapInfo.hitLength
			if quit_ or failed:
				s.playTime = failTime // 1000

			# Calculate PP
			midPPCalcException = None
			try:
				s.calculatePP()
			except Exception as e:
				# Intercept ALL exceptions and bypass them.
				# We want to save scores even in case PP calc fails
				# due to some rippoppai bugs.
				# I know this is bad, but who cares since I'll rewrite
				# the scores server again.
				log.error("Caught an exception in pp calculation, re-raising after saving score in db")
				s.pp = 0
				midPPCalcException = e

			# Set completed status
			if s.isRelax:
				# Relax always overwrites score based on PP
				# Because score on relax is not relevant
				overwritePolicy = scoreOverwrite.PP
			else:
				# Classic, on the other hands, behaves differently
				# based on user preferences. Each game mode can
				# have its own score overwrite policy
				overwritePolicy = userUtils.getScoreOverwrite(userID, s.gameMode)
			s.setCompletedStatus(overwritePolicy=overwritePolicy)

			if s.completed == -1:
				# Duplicated score
				log.warning("Duplicated score detected, this is normal right after restarting the server")
				return

			# Restrict obvious cheaters
			if s.pp >= 800 and s.gameMode == gameModes.STD and not restricted and not s.isRelax:
				userUtils.restrict(userID)
				userUtils.appendNotes(userID, "Restricted due to too high pp gain ({}pp)".format(s.pp))
				log.cm(
					"**{}** ({}) has been restricted due to too high pp gain **({}pp)**".format(username, userID, s.pp)
				)

			# Check notepad hack
			if bmk is None and bml is None:
				# No bmk and bml params passed, edited or super old client
				#log.cm("{} ({}) most likely submitted a score from an edited client or a super old client".format(username, userID))
				pass
			elif bmk != bml and not restricted:
				# bmk and bml passed and they are different, restrict the user
				userUtils.restrict(userID)
				userUtils.appendNotes(userID, "Restricted due to notepad hack")
				log.cm(
					"**{}** ({}) has been restricted due to notepad hack".format(username, userID)
				)
				return

			# Right before submitting the score, get the personal best score object (we need it for charts)
			if s.passed and s.oldPersonalBest > 0:
				# We have an older personal best. Get its rank (try to get it from cache first)
				oldPersonalBestRank = glob.personalBestCache.get(userID, s.fileMd5, relax=s.isRelax)
				if oldPersonalBestRank == 0:
					# oldPersonalBestRank not found in cache, get it from db through a scoreboard object
					oldScoreboard = scoreboard.scoreboard(username, s.gameMode, beatmapInfo, False, relax=s.isRelax)
					oldScoreboard.setPersonalBestRank()
					oldPersonalBestRank = max(oldScoreboard.personalBestRank, 0)
				oldPersonalBest = score.score(s.oldPersonalBest, oldPersonalBestRank)
			else:
				oldPersonalBestRank = 0
				oldPersonalBest = None

			# Save score in db
			s.saveScoreInDB()
			log.debug("Score id is {}".format(s.scoreID))
			glob.stats["submitted_scores"].labels(
				game_mode=scoreUtils.readableGameMode(s.gameMode),
				relax="1" if s.isRelax else "0",
				completed=str(s.completed),
			).inc()

			# Remove lock as we have the score in the database at this point
			# and we can perform duplicates check through MySQL
			log.debug("Resetting score lock key {}".format(lock_key))
			glob.redis.delete(lock_key)

			# Client anti-cheat flags
			'''ignoreFlags = 4
			if glob.debug:
				# ignore multiple client flags if we are in debug mode
				ignoreFlags |= 8
			haxFlags = (len(scoreData[17])-len(scoreData[17].strip())) & ~ignoreFlags
			if haxFlags != 0 and not restricted:
				userHelper.restrict(userID)
				userHelper.appendNotes(userID, "-- Restricted due to clientside anti cheat flag ({}) (cheated score id: {})".format(haxFlags, s.scoreID))
				log.cm("**{}** ({}) has been restricted due clientside anti cheat flag **({})**".format(username, userID, haxFlags))'''

			# Mi stavo preparando per scendere
			# Mi stavo preparando per comprare i dolci
			# Oggi e' il compleanno di mio nipote
			# Dovevamo festeggiare staseraaaa
			# ----
			# Da un momento all'altro ho sentito una signora
			# Correte, correte se ne e' sceso un muro
			# Da un momento all'altro ho sentito una signora
			# Correte, correte se ne e' sceso un muro
			# --- (io sto angora in ganottier ecche qua) ---
			# Sono scesa e ho visto ilpalazzochesenee'caduto
			# Ho preso a mio cognato, che stava svenuto
			# Mia figlia e' scesa, mia figlia ha urlato
			# "C'e' qualcuno sotto, C'e' qualcuno sotto"
			# "C'e' qualcuno sotto, C'e' qualcuno sottoooooooooo"
			# --- (scusatm che sto angor emozzionat non parlo ancora moltobbene) ---
			# Da un momento all'altro ho sentito una signora
			# Correte, correte se ne e' sceso un muro
			# Da un momento all'altro ho sentito una signora
			# Correte, correte se ne e' sceso un muro
			# -- THIS IS THE PART WITH THE GOOD SOLO (cit <3) --
			# Vedete quel palazzo la' vicino
			# Se ne sta scendendo un po' alla volta
			# Piano piano, devono prendere provvedimenti
			# Al centro qua hanno fatto una bella ristrututuitriazione
			# Hanno mess le panghina le fondane iffiori
			# LALALALALALALALALA
			if s.score < 0 or s.score > (2 ** 63) - 1:
				userUtils.ban(userID)
				userUtils.appendNotes(userID, "Banned due to negative score (score submitter)")

			# Make sure the score is not memed
			if s.gameMode == gameModes.MANIA and s.score > 1000000:
				userUtils.ban(userID)
				userUtils.appendNotes(userID, "Banned due to mania score > 1000000 (score submitter)")

			# Ci metto la faccia, ci metto la testa e ci metto il mio cuore
			if ((s.mods & mods.DOUBLETIME) > 0 and (s.mods & mods.HALFTIME) > 0) \
					or ((s.mods & mods.HARDROCK) > 0 and (s.mods & mods.EASY) > 0)\
					or ((s.mods & mods.SUDDENDEATH) > 0 and (s.mods & mods.NOFAIL) > 0):
				userUtils.ban(userID)
				userUtils.appendNotes(userID, "Impossible mod combination {} (score submitter)".format(s.mods))

			# NOTE: Process logging was removed from the client starting from 20180322
			if s.completed == 3 and "pl" in self.request.arguments:
				butterCake.bake(self, s)

			# Save replay for all passed scores
			# Make sure the score has an id as well (duplicated?, query error?)
			if s.passed and s.scoreID > 0:
				if "score" in self.request.files:
					# Save the replay if it was provided
					log.debug("Saving replay ({}) locally".format(s.scoreID))
					replay = self.request.files["score"][0]["body"]


					replayFileName = "replay_{}.osr".format(s.scoreID)

					@timeout(5, use_signals=False)
					def s3Upload():
						log.info("Uploading {} -> S3 write Bucket".format(replayFileName))
						with io.BytesIO() as f:
							f.write(replay)
							f.seek(0)
							glob.threadScope.s3.upload_fileobj(f, s3.getWriteReplayBucketName(), replayFileName)
						glob.db.execute(
							"UPDATE s3_replay_buckets SET `size` = `size` + 1 WHERE max_score_id IS NULL LIMIT 1"
						)
						log.debug("{} has been uploaded to S3".format(replayFileName))

					def saveLocally(folder):
						log.debug("Saving {} locally in {}".format(replayFileName, folder))
						with open(os.path.join(folder, replayFileName), "wb") as f:
							f.write(replay)

					def replayUploadBgWork():
						log.debug("Started replay uplaod background job")
						ok = False
						try:
							s3Upload()
							ok = True
						except Exception as e:
							m = "Error while uploading replay to S3 ({}). Saving in failed replays folder.".format(e)
							log.error(m)
							saveLocally(glob.conf["FAILED_REPLAYS_FOLDER"])
							glob.stats["replay_upload_failures"].inc()
							sentry.captureMessage(m)
						finally:
							log.debug("Replay upload background job finished. ok = {}".format(ok))

					saveLocally(glob.conf["REPLAYS_FOLDER"])
					if glob.conf.s3_enabled:
						threading.Thread(target=replayUploadBgWork, daemon=False).start()
					else:
						log.warning("S3 Replays upload disabled! Only saving locally.")

					# Send to cono ALL passed replays, even non high-scores
					if glob.conf["CONO_ENABLE"]:
						# We run this in a separate thread to avoid slowing down scores submission,
						# as cono needs a full replay
						threading.Thread(target=lambda: glob.redis.publish(
							"cono:analyze", json.dumps({
								"score_id": s.scoreID,
								"relax": s.isRelax,
								"beatmap_id": beatmapInfo.beatmapID,
								"user_id": s.playerUserID,
								"game_mode": s.gameMode,
								"pp": s.pp,
								"completed": s.completed,
								"replay_data": base64.b64encode(
									replayHelper.buildFullReplay(
										s.scoreID,
										rawReplay=self.request.files["score"][0]["body"]
									)
								).decode(),
							})
						), daemon=False).start()
				elif not restricted:
					# Restrict if no replay was provided
					userUtils.restrict(userID)
					userUtils.appendNotes(
						userID,
						"Restricted due to missing replay while submitting a score "
						"(most likely they used a score submitter)"
					)
					log.cm("**{}** ({}) has been restricted due to replay not found on map {}".format(
						username, userID, s.fileMd5
					))

			# Update beatmap playcount (and passcount)
			beatmap.incrementPlaycount(s.fileMd5, s.passed)

			# Let the api know of this score
			if s.scoreID:
				glob.redis.publish("api:score_submission", s.scoreID)

			# Auto !last
			if s.completed == 3:
				userAutoLast = userUtils.getAutoLast(userID, s.isRelax)
				if userAutoLast == autoLast.MESSAGE:
					fokabot.last(userID)
				elif userAutoLast == autoLast.NOTIFICATION:
					bancho.notification(
						userID,
						f"Your latest score is worth\n{s.pp:.2f} pp{' (personal best!)' if s.completed == 3 else ''}"
					)

			# Update leaderboard relax mode
			if userUtils.isRelaxLeaderboard(userID) != s.isRelax:
				log.info("Notifying delta about relax switch")
				glob.redis.publish("peppy:switch_relax", json.dumps({"user_id": userID, "relax": s.isRelax}))

			# Re-raise pp calc exception after saving score, cake, replay etc
			# so Sentry can track it without breaking score submission
			if midPPCalcException is not None:
				raise ppCalcException(midPPCalcException)

			# If there was no exception, update stats and build score submitted panel
			# Get "before" stats for ranking panel (only if passed)
			if s.passed:
				# Get old stats and rank
				oldUserStats = glob.userStatsCache.get(userID, s.gameMode)
				oldRank = userUtils.getGameRank(userID, s.gameMode, relax=s.isRelax)

			# Always update users stats (total/ranked score, playcount, level, acc and pp)
			# even if not passed
			log.debug("Updating {}'s stats...".format(username))
			userUtils.updateStats(userID, s, relax=s.isRelax)

			# Update personal beatmaps playcount
			userUtils.incrementUserBeatmapPlaycount(userID, s.gameMode, beatmapInfo.beatmapID)

			# Get "after" stats for ranking panel
			# and to determine if we should update the leaderboard
			# (only if we passed that song)
			if s.passed:
				# Get new stats
				newUserStats = userUtils.getUserStats(userID, s.gameMode, relax=s.isRelax)
				glob.userStatsCache.update(userID, s.gameMode, newUserStats)

				# Update leaderboard (global and country) if score/pp has changed
				if s.completed == 3 and newUserStats["pp"] != oldUserStats["pp"]:
					leaderboardHelper.update(userID, newUserStats["pp"], s.gameMode, relax=s.isRelax)
					leaderboardHelper.updateCountry(userID, newUserStats["pp"], s.gameMode, relax=s.isRelax)

			# Update total hits
			userUtils.updateTotalHits(score=s, relax=s.isRelax)
			# TODO: max combo

			# Update latest activity
			userUtils.updateLatestActivity(userID)

			# IP log
			userUtils.IPLog(userID, ip)

			# Score submission and stats update done
			log.debug("Score submission and user stats update done!")

			# Score has been submitted, do not retry sending the score if
			# there are exceptions while building the ranking panel
			keepSending = False

			# At the end, check achievements
			if s.passed:
				new_achievements = secret.achievements.utils.unlock_achievements(s, beatmapInfo, newUserStats)

			# Output ranking panel only if we passed the song
			# and we got valid beatmap info from db
			if beatmapInfo is not None and beatmapInfo != False and s.passed:
				log.debug("Started building ranking panel")

				# Trigger bancho stats cache update
				glob.redis.publish("peppy:update_cached_stats", userID)

				# Get personal best after submitting the score
				newScoreboard = scoreboard.scoreboard(username, s.gameMode, beatmapInfo, False, relax=s.isRelax)
				newScoreboard.setPersonalBestRank()
				personalBestID = newScoreboard.getPersonalBestID()
				assert personalBestID is not None
				currentPersonalBest = score.score(personalBestID, newScoreboard.personalBestRank)

				# Get rank info (current rank, pp/score to next rank, user who is 1 rank above us)
				rankInfo = leaderboardHelper.getRankInfo(userID, s.gameMode)

				# Output dictionary
				if newCharts:
					log.debug("Using new charts")
					dicts = [
						collections.OrderedDict([
							("beatmapId", beatmapInfo.beatmapID),
							("beatmapSetId", beatmapInfo.beatmapSetID),
							("beatmapPlaycount", beatmapInfo.playcount + 1),
							("beatmapPasscount", beatmapInfo.passcount + (s.completed == 3)),
							("approvedDate", "")
						]),
						BeatmapChart(
							oldPersonalBest if s.completed == 3 else currentPersonalBest,
							currentPersonalBest if s.completed == 3 else s,
							beatmapInfo.beatmapID,
						),
						OverallChart(
							userID, oldUserStats, newUserStats, s, new_achievements, oldRank, rankInfo["currentRank"]
						)
					]
				else:
					log.debug("Using old charts")
					dicts = [
						collections.OrderedDict([
							("beatmapId", beatmapInfo.beatmapID),
							("beatmapSetId", beatmapInfo.beatmapSetID),
							("beatmapPlaycount", beatmapInfo.playcount),
							("beatmapPasscount", beatmapInfo.passcount),
							("approvedDate", "")
						]),
						collections.OrderedDict([
							("chartId", "overall"),
							("chartName", "Overall Ranking"),
							("chartEndDate", ""),
							("beatmapRankingBefore", oldPersonalBestRank),
							("beatmapRankingAfter", newScoreboard.personalBestRank),
							("rankedScoreBefore", oldUserStats["rankedScore"]),
							("rankedScoreAfter", newUserStats["rankedScore"]),
							("totalScoreBefore", oldUserStats["totalScore"]),
							("totalScoreAfter", newUserStats["totalScore"]),
							("playCountBefore", newUserStats["playcount"]),
							("accuracyBefore", float(oldUserStats["accuracy"])/100),
							("accuracyAfter", float(newUserStats["accuracy"])/100),
							("rankBefore", oldRank),
							("rankAfter", rankInfo["currentRank"]),
							("toNextRank", rankInfo["difference"]),
							("toNextRankUser", rankInfo["nextUsername"]),
							("achievements", ""),
							("achievements-new", secret.achievements.utils.achievements_response(new_achievements)),
							("onlineScoreId", s.scoreID)
						])
					]
				output = "\n".join(zingonify(x) for x in dicts)

				# Some debug messages
				log.debug("Generated output for online ranking screen!")
				log.debug(output)

				# send message to #announce if we're rank #1
				if newScoreboard.personalBestRank == 1 and s.completed == 3 and not restricted:
					annmsg =\
						"[https://ripple.moe/?u={} {}] " \
						"achieved rank #1 on " \
						"[https://osu.ppy.sh/b/{} {}] ({}, {})".format(
						userID,
						username.encode().decode("ASCII", "ignore"),
						beatmapInfo.beatmapID,
						beatmapInfo.songName.encode().decode("ASCII", "ignore"),
						gameModes.getGamemodeFull(s.gameMode),
						"relax" if s.isRelax else "classic"
					)
					fokaM = None
					try:
						fokabot.message(annmsg, "#announce-relax" if s.isRelax else "#announce")
					except requests.Timeout as e:
						fokaM ="FokaBot #1 timeout."
					except requests.ConnectionError as e:
						fokaM = "FokaBot #1 connection error."
					finally:
						if fokaM is not None:
							log.error(fokaM)
							sentry.captureMessage(fokaM)

				# Write message to client
				self.write(output)
			else:
				# No ranking panel, send just "ok"
				self.write("error: no")

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
		except exceptions.need2FAException:
			# Send error pass to notify the user
			# resend the score at regular intervals
			# for users with memy connection
			self.set_status(408)
			self.write("error: 2fa")
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
				log.error("Unknown error in {}!\n```{}\n{}```".format(self.MODULE_NAME, sys.exc_info(), traceback.format_exc()))
				if glob.conf.sentry_enabled:
					yield tornado.gen.Task(self.captureException, exc_info=True)
			except:
				pass

			# Every other exception returns a 408 error (timeout)
			# This avoids lost scores due to score server crash
			# because the client will send the score again after some time.
			if keepSending:
				self.set_status(408)
