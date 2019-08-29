import threading

from common.log import logUtils as log
import helpers.s3
import objects.glob


class ThreadScope(threading.local):
    def __init__(self):
        log.info("Created thread local scope for thread {}".format(threading.get_ident()))
        self._s3 = None
        self._db = None

    @property
    def s3(self):
        if self._s3 is None:
            self._s3 = helpers.s3.clientFactory()
            log.info("Created a new S3 client for thread {}".format(threading.get_ident()))
        return self._s3

    @property
    def db(self):
        if self._db is None:
            self._db = objects.glob.db.connectionFactory()
            log.info("Created a new db connection for thread {}".format(threading.get_ident()))
        return self._db

    def dbClose(self):
        try:
            self._db.close()
        except:
            pass
        log.info("Closed and destroyed db connection for thread {}".format(threading.get_ident()))
        self._db = None
