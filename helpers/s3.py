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
        "SELECT `name`, max_score_id FROM s3_replay_buckets WHERE max_score_id IS NOT NULL "
        "ORDER BY abs(max_score_id - %s) LIMIT 1",
        (scoreID,)
    )
    if r is not None and scoreID <= r["max_score_id"]:
        log.debug("s3 replay buckets resolve: {} -> {}".format(scoreID, r["name"]))
        return r["name"]
    log.debug("s3 replay buckets resolve: {} -> WRITE BUCKET".format(scoreID))
    return getWriteReplayBucketName()


def clientFactory():
    return boto3.Session(region_name=objects.glob.conf["S3_REGION"]).client(
        "s3",
        endpoint_url=objects.glob.conf["S3_ENDPOINT_URL"],
        aws_access_key_id=objects.glob.conf["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=objects.glob.conf["S3_SECRET_ACCESS_KEY"]
    )
