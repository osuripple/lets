from helpers import logHelper as log
from functools import wraps
import traceback
import sys

def trackExceptions(moduleName=""):
	def _trackExceptions(func):
		def _decorator(request, *args, **kwargs):
			try:
				response = func(request, *args, **kwargs)
				return response
			except:
				log.error("Unknown error{}!\n```\n{}\n{}```".format(" in "+moduleName if moduleName != "" else "", sys.exc_info(), traceback.format_exc()), True)
		return wraps(func)(_decorator)
	return _trackExceptions
