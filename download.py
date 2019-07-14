import os
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
import asyncio
import urllib.parse as parse
import sys
import socket
import threading
import time
import json
import schedule
import boto3
import logging
from datetime import datetime, timezone, timedelta

import util

basebasedir = '/data/photod'
logdir = '/logs/photod'
os.makedirs(logdir, exist_ok=True)
starttime = datetime.now().strftime('%Y%m%d-%H%M')
logging.getLogger().setLevel(logging.WARNING)
logger = logging.getLogger('photod')
logger.setLevel(logging.DEBUG)
logFormatter = logging.Formatter(fmt='%(asctime)s %(levelname)s: %(message)s',
                                 datefmt='%Y%m%d-%H%S')
fileHandler = logging.FileHandler(os.path.join(logdir, starttime))
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

logger.info('started download.py at {0}'.format(starttime))

def download():
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(os.environ.get('S3_BUCKET'))

    catalogPrefix = os.path.join(os.environ.get('S3_PREFIX'), os.environ.get('EMAIL'), 'catalog')
    basedir = os.path.join(basebasedir, os.environ.get('EMAIL'))
    os.makedirs(basedir, exist_ok=True)
    logger.debug('bucket: {0}, catalogPrefix: {1}'.format(
        os.environ.get('S3_BUCKET'), catalogPrefix))
    albums = bucket.Object(catalogPrefix + '/album').get()['Body'].read().decode('utf-8').split('\n')
    p = 0
    while len(albums) > p:
        if albums[p] == '':
            del albums[p]
        p += 1
    logger.info('{0} albums found'.format(len(albums)))
    albumCurrent = 0
    albumSuccessCount = 0
    albumFailureCount = 0
    for album in albums:
        photoCurrent = 0
        successCount = 0
        failureCount = 0
        albumId = album.split(' ')[0]
        albumName = album.split(' ')[1]
        photos = bucket.Object(catalogPrefix + '/albums/' + albumId
            ).get()['Body'].read().decode('utf-8').split('\n')
        p = 0
        while len(photos) > p:
            if photos[p] == '':
                del photos[p]
            p += 1
        logger.info('{0}/{1}: {2} photos found in album "{3}"'.format(
            albumCurrent + 1, len(albums), len(photos), albumName))

        albumDest = os.path.join(basedir, albumName)
        os.makedirs(albumDest, exist_ok=True)
        os.chmod(albumDest, 0o777)
        for photo in photos:
            photoId = photo.split(' ')[0]
            photoName = photo.split(' ')[1]
            logger.debug('{0}/{1}-{2}/{3}: downloading photo, filename="{4}"'.format(
                albumCurrent + 1, len(albums), photoCurrent + 1, len(photos), photoName))
            src = os.path.join(os.environ.get('S3_PREFIX'), os.environ.get('EMAIL'), albumId, photoId)

            # replace '/' in photoName
            photoName = photoName.replace('/', '_')
            # check whether duplicate filename
            originalPhotoName = '.'.join(photoName.split('.')[:-1])
            extension = photoName.split('.')[-1]
            existsTryCount = 0
            while os.path.exists(os.path.join(basedir, albumName, photoName)):
                # change filename
                existsTryCount += 1
                photoName = '{0}_{1}.{2}'.format(originalPhotoName, existsTryCount, extension)
            if existsTryCount > 0:
                logger.warning('{0}/{1}-{2}/{3}: duplicated filename="{4}", changed to="{5}"'.format(
                    albumCurrent + 1, len(albums), photoCurrent + 1, len(photos),
                    originalPhotoName, photoName))

            dest = os.path.join(basedir, albumName, photoName)
            try:
                bucket.Object(src).download_file(dest)
                os.chmod(dest, 0o777)
                successCount += 1
            except Exception as e:
                logger.exception('download()', stack_info=True)
                failureCount += 1
            photoCurrent += 1

        logger.info('{0}/{1}: downloaded photos in album "{2}", total={3}, success={4}, failure={5}'.format(
            albumCurrent + 1, len(albums), albumName, len(photos), successCount, failureCount))
        albumCurrent += 1
        if successCount == len(albums):
            albumSuccessCount += 1
        else:
            albumFailureCount += 1

    logger.info('downloaded albums, total={0}, success={1}, failure={2}'.format(
        len(albums),  albumSuccessCount, albumFailureCount))

if __name__ == '__main__':
    envse = ['S3_BUCKET', 'S3_PREFIX', 'EMAIL']

    f = util.environ(envse, 'error')

    if f:
        print('error: some environment variables are not set. exiting.', file=sys.stderr)
        sys.exit(1)

    download()
