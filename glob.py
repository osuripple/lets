import fileLocks

try:
	with open("version") as f:
		VERSION = f.read()
except:
	VERSION = "¯\_(xd)_/¯"
db = None
conf = None
debug = False
pool = None
discord = False
fLocks = fileLocks.fileLocks()
sentry = False
userIDCache = {}
