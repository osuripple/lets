from helpers import requestHelper

class handler(requestHelper.asyncRequestHandler):
	def asyncGet(self):
		self.set_status(302)
		self.add_header("location", "https://ripple.moe/index.php?p=2")
		#self.finish()
