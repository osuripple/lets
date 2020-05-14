import threading

from common.log import logUtils as log
import helpers.s3
import objects.glob


class ThreadScope(threading.local):
    def __init__(self):
        log.debug("Created thread local scope for thread {}".format(threading.get_ident()))
        self._s3 = None
        self._s3Screenshots = None
        self._db = None

    def _s3_prop(self, attr, **kwargs):
        if getattr(self, attr) is None:
            setattr(self, attr, helpers.s3.clientFactory(**kwargs))
            log.debug("Created a new S3 client for thread {}".format(threading.get_ident()))
        return getattr(self, attr)

    @property
    def s3(self):
        return self._s3_prop(
            "_s3",
            region=objects.glob.conf["S3_REGION"],
            endpoint=objects.glob.conf["S3_ENDPOINT_URL"],
            accessKeyId=objects.glob.conf["S3_ACCESS_KEY_ID"],
            secretAccessKey=objects.glob.conf["S3_SECRET_ACCESS_KEY"],
        )

    @property
    def s3Screenshots(self):
        return self._s3_prop(
            "_s3Screenshots",
            region=objects.glob.conf["S3_SCREENSHOTS_REGION"],
            endpoint=objects.glob.conf["S3_SCREENSHOTS_ENDPOINT_URL"],
            accessKeyId=objects.glob.conf["S3_ACCESS_KEY_ID"],
            secretAccessKey=objects.glob.conf["S3_SECRET_ACCESS_KEY"],
        )

    @property
    def db(self):
        if self._db is None:
            self._db = objects.glob.db.connectionFactory()
            log.debug("Created a new db connection for thread {}".format(threading.get_ident()))
        return self._db

    def dbClose(self):
        tid = threading.get_ident()
        if self._db is None:
            log.info(
                "Closing db connection, but thread {} has no db connection.".format(tid)
            )
            return
        try:
            self._db.close()
        except Exception as e:
            log.warning("Error ({}) while closing db connection for thread {}. Failing silently.".format(e, tid))
            pass
        log.info("Closed and destroyed db connection for thread {}".format(tid))
        self._db = None
