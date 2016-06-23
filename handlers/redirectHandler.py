from helpers import requestHelper

class handler(requestHelper.asyncRequestHandler):
	def initialize(self, destination):
		self.destination = destination

	def asyncGet(self, args=()):
		self.set_status(302)
		self.add_header("location", self.destination.format(args))
