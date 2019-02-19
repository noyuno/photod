import os
from requests_oauthlib import OAuth2Session
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

callback_uri = '/callback'
authorization_base_url = "https://accounts.google.com/o/oauth2/v2/auth"
token_url = "https://www.googleapis.com/oauth2/v4/token"
scope = ['https://www.googleapis.com/auth/photoslibrary.readonly',
         'https://www.googleapis.com/auth/userinfo.profile',
         'https://www.googleapis.com/auth/userinfo.email']
redirect_response = None
token = None
s3_root = 'backup/photod'

basedir = '/data/photod/out'
os.makedirs(basedir + '/logs', exist_ok=True)
starttime = datetime.now().strftime('%Y%m%d-%H%M')
logging.getLogger().setLevel(logging.WARNING)
logger = logging.getLogger('photod')
logger.setLevel(logging.DEBUG)
logFormatter = logging.Formatter(fmt='%(asctime)s %(levelname)s: %(message)s',
                                 datefmt='%Y%m%d-%H%S')
fileHandler = logging.FileHandler(basedir + '/logs/{0}'.format(starttime))
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

logger.info('started photod at {0}'.format(starttime))

def check_environ(keys, header):
    ret = False
    for k in keys:
        if os.environ.get(k) is None:
            ret = True
            print('{0}: {1} is not set'.format(header, k), file=sys.stderr)
    return ret

def message(data, stderr=False):
    if type(data) is str:
        data = { 'message': data }
    if stderr:
        logger.error(data.get('message'))
    else:
        logger.info(data.get('message'))
    if data.get('message') is not None:
        data['message'] = 'photod: ' + data['message']
    r = requests.post('http://' + os.environ.get('DISCORDBOT'),
                  data=json.dumps(data).encode('utf-8'),
                  headers={'content-type': 'application/json'})
    if r.status_code != 200:
        logger.error('failure to send message to discordbot, status={0}'.format(r.status_code))

class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global redirect_response, callback_uri
        pp = parse.urlparse(self.path)
        query = parse.parse_qs(self.path)
        if pp.path == callback_uri:
            # debug
            print('callback from google')

            if query.get('error') is not None:
                message('oauth2 error, message={0}'.format(query.get('error')), True)
            else:
                redirect_response = os.environ.get('BASE_URL') + self.path

            self.send_response(200)
            self.send_header('content-type', 'text')
            self.end_headers()
            self.wfile.write('authorized. close this tab.\n\nphotod'.encode('utf-8'))
        else:
            self.send_response(501)
            self.send_header('content-type', 'text')
            self.end_headers()
            self.wfile.write('http 501\nphotod'.encode('utf-8'))

    def do_POST(self):
        self.send_response(501)
        self.send_header('content-type', 'text')
        self.end_headers()
        self.wfile.write('http 501\nphotod'.encode('utf-8'))

def httpserver(loop):
    asyncio.set_event_loop(loop)
    print('launch http server')
    server = HTTPServer(('photod', 80), APIHandler)
    server.serve_forever()

def scheduler(loop):
    asyncio.set_event_loop(loop)
    print('launch scheduler')
    schedule.every(24).hours.do(refresh_token_backup)

    while True:
        schedule.run_pending()
        time.sleep(1)

def refresh_token_backup():
    try:
        global token_url, token
        extra = {
            'client_id': os.environ.get('GOOGLE_OAUTH_CLIENT'),
            'client_secret': os.environ.get('GOOGLE_OAUTH_SECRET')
        }
        google = OAuth2Session(os.environ.get('GOOGLE_OAUTH_CLIENT'), token=token)
        token = google.refresh_token(token_url, refresh_token=token['access_token'], **extra)
        logger.debug('refreshed. token={0}'.format(token))
        backup(google)
    except Exception as e:
        err = e.with_traceback(sys.exc_info()[2])
        errtext = 'error: {0}({1})'.format(err.__class__.__name__, str(err))
        message(errtext)

def album_catalog(id, name):
    os.makedirs('{0}/catalog/{1}'.format(basedir, starttime), exist_ok=True)
    cat = open('{0}/catalog/{1}/album'.format(basedir, starttime), 'a', encoding='utf-8')
    cat.write('{0} {1}'.format(id, name))
    cat.close()

def photo_catalog(albumid, id, name):
    os.makedirs('{0}/catalog/{1}/albums'.format(basedir, starttime), exist_ok=True)
    cat = open('{0}/catalog/{1}/albums/{2}'.format(basedir, starttime, albumid), 'a', encoding='utf-8')
    cat.write('{0} {1}'.format(id, name))
    cat.close()

def put_album_catalog(bucket, prefix):
    cat = open('{0}/catalog/{1}/album'.format(basedir, starttime), 'rb')
    bucket.Object(prefix).put(Body=cat)
    cat.close()

def put_photo_catalog(bucket, prefix, albumid):
    cat = open('{0}/catalog/{1}/albums/{2}'.format(basedir, starttime, albumid), 'rb')
    bucket.Object(prefix).put(Body=cat)
    cat.close()

def put_photos(google, bucket, r, rp, already_saved, albumCurrent, photoCurrent, album, item, prefix):
    src = '{0}{1}'.format(item.get('baseUrl'), '=w10000-h10000')
    dest = prefix + item.get('id')
    if dest in already_saved:
        # debug
        logger.debug('{0}/{1}-{2}/{3}: already exists:{4} {5}'.format(
            albumCurrent + 1, len(r.get('albums')),
            photoCurrent + 1, len(rp.get('mediaItems')),
            item.get('id'), item.get('filename')))
        return 3
    else:
        # debug
        logger.debug('{0}/{1}-{2}/{3}: uploading photo: filename="{4}" to {5}'.format(
            albumCurrent + 1, len(r.get('albums')),
            photoCurrent + 1, len(rp.get('mediaItems')),
            item.get('filename'), dest))
        imageres = requests.get(src)
        if imageres.status_code != 200:
            # retry
            time.sleep(5)
            imageres = requests.get('{0}{1}'.format(item.get('baseUrl'), '=w10000-h10000'))
            if imageres.status_code != 200:
                logger.error('error {0} at {1}/{2}-{3}/{4}: {5} {6}\n'.format(
                    imageres.status_code,
                    albumCurrent + 1, len(r.get('albums')),
                    photoCurrent + 1, len(rp.get('mediaItems')),
                    filename, src))
                #failureCount += 1
                return 1

        try:
            bucket.Object(dest).put(Body=imageres.content)
        except Exception as e:
            err = e.with_traceback(sys.exc_info()[2])
            err = 'error {0} at {1}/{2}-{3}/{4}: {5} {6} ({7})'.format(
                err.__class__.__name__,
                albumCurrent + 1, len(r.get('albums')),
                photoCurrent + 1, len(rp.get('mediaItems')),
                filename, src, str(err))
            logger.error(err)
            #failureCount += 1
            return 2

        # uploaded a photo
        #successCount += 1
    #photoCurrent += 1
    return 0

def put_albums(google, bucket, email, r, albumCurrent, album):
    message('{0}/{1} {2}: {3} items\n'.format(
        albumCurrent, len(r.get('albums')), album.get('title'), album.get('mediaItemsCount')))
    successCount = 0
    failureCount = 0
    alreadyCount = 0
    photoCurrent = 0

    #for bucket in s3.buckets.all():
    #    message(bucket.name)
    prefix = '/'.join([s3_root, email, album.get('id'), ''])
    logger.debug('prefix: {0}'.format(prefix))
    #l = bucket.objects.filter(Prefix=prefix)
    already_saved = [ o.key for o in bucket.objects.filter(Prefix=prefix)]
    # s3 pagenation has not implemented yet
    #logger.debug('{0}'.format(l))

    #already_saved = []
    #if l is not None and 'Contents' in l:
    #    already_saved = [content['Key'] for content in l['Contents']]
    if len(already_saved) > 0:
        logger.debug('{0}/{1}: already saved: {2} photos found. first record={3}'.format(
            albumCurrent, len(r.get('albums')),
            len(already_saved), already_saved[0]))
    else:
        logger.debug('{0}/{1}: not found that already saved photo'.format(
                     albumCurrent, len(r.get('albums'))))

    # append (album id, album name) pair to albumcat
    album_catalog(album.get('id'), album.get('title'))

    rp = google.post('https://photoslibrary.googleapis.com/v1/mediaItems:search',
                     data={ 'pageSize': 100, 'albumId': album.get('id') }).json()
    logger.debug('{0}/{1}: nextPageToken={2}'.format(
        albumCurrent, len(r.get('albums')), rp.get('nextPageToken') is not None))
    for item in rp.get('mediaItems'):
        ret = put_photos(google, bucket, r, rp, already_saved, albumCurrent, photoCurrent, album, item, prefix)
        if ret == 0:
            successCount += 1
            photo_catalog(album.get('id'), item.get('id'), item.get('filename'))
        elif ret == 1:
            failureCount += 1
        elif ret == 2:
            failureCount += 1
        elif ret == 3:
            alreadyCount += 1
            photo_catalog(album.get('id'), item.get('id'), item.get('filename'))
        photoCurrent += 1

    while rp.get('nextPageToken') is not None:
        # debug
        logger.debug('{0}/{1}: put_albums(): nextPageToken found in current album'.format(
                     albumCurrent, len(r.get('albums'))))
        rp = google.post('https://photoslibrary.googleapis.com/v1/mediaItems:search',
                            data={ 'pageSize': 100, 'albumId': album.get('id'),
                                'pageToken': rp.get('nextPageToken')        }).json()
        for item in rp.get('mediaItems'):
            ret = put_photos(google, bucket, r, rp, already_saved, albumCurrent, photoCurrent, album, item, prefix)
            if ret == 0:
                successCount += 1
                photo_catalog(album.get('id'), item.get('id'), item.get('filename'))
            elif ret == 1:
                failureCount += 1
            elif ret == 2:
                failureCount += 1
            elif ret == 3:
                alreadyCount += 1
                photo_catalog(album.get('id'), item.get('id'), item.get('filename'))
            photoCurrent += 1

    catalog_prefix = '/'.join([s3_root, email, 'catalog', 'albums', album.get('id')])
    #catalog_prefix = s3_root + '/' + email + '/catalog/albums/' + album.get('id')
    logger.debug('{0}/{1}: put photo catalog to={2}'.format(
                 albumCurrent, len(r.get('albums')), catalog_prefix))
    put_photo_catalog(bucket, catalog_prefix, album.get('id'))

    ret = 0
    emoji = ''
    if int(album.get('mediaItemsCount')) == successCount + alreadyCount:
        #successAlbums += 1
        ret = 0
        emoji = 'ok'
    else:
        #failureAlbums += 1
        ret = 1
        emoji = 'bad'
    message('{0} album {1}: total {2}, success {3}, already {4}, failure {5}\n'.format(
        util.emoji(emoji), album.get('title'), album.get('mediaItemsCount'), successCount, alreadyCount, failureCount))
    #albumCurrent += 1
    return ret

def backup(google):
    logger.debug('opening s3')
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(os.environ.get('S3_BUCKET'))

    # get userid
    userinfo = google.get('https://people.googleapis.com/v1/people/me?personFields=emailAddresses').json()
    # debug
    #print('userinfo={0}'.format(userinfo))
    email = None
    for i in userinfo.get('emailAddresses'):
        if i.get('metadata').get('primary') == True:
            email = i.get('value')
            break
    if email is None:
        message('error: cannot find primary email address.')
        print(userinfo)
        sys.exit(1)

    r = google.get('https://photoslibrary.googleapis.com/v1/albums').json()
    message('{0} albums found in this page, nextPageToken={1}\n'.format(
        len(r.get('albums')), r.get('nextPageToken') is not None))

    successAlbums = 0
    failureAlbums = 0
    albumCurrent = 0

    for album in r.get('albums'):
        ret = put_albums(google, bucket, email, r, albumCurrent, album)
        if ret == 0:
            successAlbums += 1
        else:
            failureAlbums += 1
        albumCurrent += 1

    while r.get('nextPageToken') is not None:
        message('put_albums(): nextPageToken found')
        r = google.get('https://photoslibrary.googleapis.com/v1/albums').json()

        for album in r.get('albums'):
            ret = put_albums(google, bucket, email, album)
            if ret == 0:
                successAlbums += 1
            else:
                failureAlbums += 1
            albumCurrent += 1

    catalog_prefix = '/'.join([s3_root, email, 'catalog', 'album'])
    logger.debug('put album catalog to={0}'.format(catalog_prefix))
    put_album_catalog(bucket, catalog_prefix)

    emoji = ''
    if len(r.get('albums')) == successAlbums:
        emoji = 'ok'
    else:
        emoji = 'bad'
    message('{0} photod: finished: total {1}, success {2}, failure {3}\n'.format(
        util.emoji(emoji), len(r.get('albums')), successAlbums, failureAlbums))

if __name__ == '__main__':
    envse = ['GOOGLE_OAUTH_CLIENT', 'GOOGLE_OAUTH_SECRET', 'DISCORDBOT', 'BASE_URL']

    f = check_environ(envse, 'error')

    if f:
        print('error: some environment variables are not set. exiting.', file=sys.stderr)
        sys.exit(1)

    try:
        print('listen at {0}'.format(socket.gethostbyname_ex(socket.gethostname())))
        httploop = asyncio.new_event_loop()
        threading.Thread(target=httpserver, args=(httploop,)).start()

        scheduleloop = asyncio.new_event_loop()
        threading.Thread(target=scheduler, args=(scheduleloop,)).start()

        redirect_uri = '{0}{1}'.format(os.environ.get('BASE_URL'), callback_uri)
        google = OAuth2Session(os.environ.get('GOOGLE_OAUTH_CLIENT'), scope=scope,
                               redirect_uri=redirect_uri)
        authorization_url, state = google.authorization_url(authorization_base_url,
                                                            access_type="offline",
                                                            prompt="select_account")
        message('Please authenticate the application: {0}'.format(authorization_url))

        # wait 5 minutes
        count = 0
        while count < 60 * 5:
            if redirect_response is not None:
                break
            time.sleep(1)
            count += 1
        if redirect_response is None:
            message('timed out', True)
            sys.exit(1)
        token = google.fetch_token(token_url,
                                   client_secret=os.environ.get('GOOGLE_OAUTH_SECRET'),
                                   authorization_response=redirect_response)
        # debug
        # print('authorized. token={0}'.format(token))
        backup(google)
    except Exception as e:
        err = e.with_traceback(sys.exc_info()[2])
        errtext = 'error: {0}({1})'.format(err.__class__.__name__, str(err))
        try:
            message(errtext, stderr=True)
        except Exception as e:
            err = e.with_traceback(sys.exc_info()[2])
            err = 'error: {0}({1})'.format(err.__class__.__name__, str(err))
            logger.error(err)

