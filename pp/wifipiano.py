import subprocess

class piano:
	# Folder where wifipiano is placed
	PP_FOLDER = "../ripple_ppcalc"

	def __init__(self, __beatmap, __score):
		self.beatmap = __beatmap
		self.score = __score
		self.pp = 0
		self.getPP()

	def getPP(self):
		# Base command
		map = "maps/{}.osu".format(self.beatmap.beatmapID)
		command = "{path}/wifipiano {mapFile}".format(path=self.PP_FOLDER, mapFile=map)

		# Add params
		command += "-stars {}".format(self.beatmap.starsMania)
		command += "-od {}".format(self.beatmap.OD)
		command += "-obj {}".format(self.score.c50+self.score.c100+self.score.c300+self.score.cKatu+self.score.cGeki+self.score.cMiss)
		command += "-score {}".format(self.score.score)
		command += "-acc {}".format(self.score.accuracy)
		command += "-mods {}".format(self.score.mods)

		# Run wifipiano and get output
		process = subprocess.run(command, shell=True, stdout=subprocess.PIPE)
		output = process.stdout.decode("utf-8")
		return float(output)
