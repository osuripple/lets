import fileLocks
import userStatsCache
import personalBestCache
import fileBuffer

try:
	with open("version") as f:
		VERSION = f.read()
except:
	VERSION = "¯\_(xd)_/¯"
db = None
conf = None
application = None
pool = None

busyThreads = 0
debug = False
discord = False
sentry = False
cloudflare = False

# Cache and objects
fLocks = fileLocks.fileLocks()
userIDCache = {}
userStatsCache = userStatsCache.userStatsCache()
personalBestCache = personalBestCache.personalBestCache()
fileBuffers = fileBuffer.buffersList()
