import threading

import boto3

import objects.glob
from common.log import logUtils as log


def getClient():
    return objects.glob.s3Connections[threading.get_ident()]


def clientFactory():
    log.info("Created a new S3 client for thread {}".format(threading.get_ident()))
    return boto3.Session(region_name=objects.glob.conf["S3_REGION"]).client(
        "s3",
        endpoint_url=objects.glob.conf["S3_ENDPOINT_URL"],
        aws_access_key_id=objects.glob.conf["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=objects.glob.conf["S3_SECRET_ACCESS_KEY"]
    )
