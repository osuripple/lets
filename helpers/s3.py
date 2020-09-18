import threading

import boto3

import objects.glob
from common.log import logUtils as log


# def getClient():
#     return objects.glob.s3Connections[threading.get_ident()]


def getWriteReplayBucketName():
    r = objects.glob.db.fetch("SELECT `name` FROM s3_replay_buckets WHERE max_score_id IS NULL LIMIT 1")
    if r is None:
        raise RuntimeError("No write replays S3 write bucket!")
    return r["name"]


def getReadReplayBucketName(scoreID):
    r = objects.glob.db.fetch(
        """SELECT name FROM (
            SELECT `name`,
            IFNULL((SELECT max_score_id + 1 FROM s3_replay_buckets WHERE id = x.id - 1), 0) AS min_score_id,
            IFNULL(max_score_id, ~0) AS max_score_id
            FROM s3_replay_buckets AS x
        ) AS x
        WHERE %s > min_score_id AND %s < max_score_id
        LIMIT 1""",
        (scoreID, scoreID)
    )
    if r is not None:
        log.debug("s3 replay buckets resolve: {} -> {}".format(scoreID, r["name"]))
        return r["name"]
    log.debug("s3 replay buckets resolve: {} -> WRITE BUCKET".format(scoreID))
    return getWriteReplayBucketName()


def clientFactory(*, region, endpoint, accessKeyId, secretAccessKey):
    return boto3.Session(region_name=region).client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=accessKeyId,
        aws_secret_access_key=secretAccessKey
    )
