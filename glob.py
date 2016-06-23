import fileLocks
import userStatsCache
import personalBestCache

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
sentry = False
cloudflare = False

# Cache and objects
fLocks = fileLocks.fileLocks()
userIDCache = {}
userStatsCache = userStatsCache.userStatsCache()
personalBestCache = personalBestCache.personalBestCache()
