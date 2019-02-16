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

callback_uri = '/callback'
authorization_base_url = "https://accounts.google.com/o/oauth2/v2/auth"
token_url = "https://www.googleapis.com/oauth2/v4/token"
scope = ['https://www.googleapis.com/auth/photoslibrary.readonly']
redirect_response = None
google = None
token = None

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
        print(data.get('message'), file=sys.stderr)
    else:
        print(data.get('message'))
    if data.get('message') is not None:
        data['message'] = 'photod: ' + data['message']
    requests.post('http://' + os.environ.get('DISCORDBOT'),
                  data=json.dumps(data).encode('utf-8'),
                  headers={'content-type': 'application/json'})

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
        global token_url, google, token
        extra = {
            'client_id': os.environ.get('GOOGLE_OAUTH_CLIENT'),
            'client_secret': os.environ.get('GOOGLE_OAUTH_SECRET')
        }
        token = google.refresh_token(token_url, refresh_token=token['access_token'], **extra)
        print('refreshed. token={0}'.format(token))

        # TODO BACKUP

    except Exception as e:
        err = e.with_traceback(sys.exc_info()[2])
        errtext = 'error: {0}({1})'.format(err.__class__.__name__, str(err))
        message(errtext)

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
        print('authorized. token={0}'.format(token))
        # get userid
        userinfo = google.get('https://www.googleapis.com/oauth2/v1/userinfo').json()
        print(userinfo)
        r = google.get('https://photoslibrary.googleapis.com/v1/albums').json()
        text = '{0} albums found\n'.format(len(r.get('albums')))
        for album in r.get('albums'):
            text += '{0}: {1} items\n'.format(album.get('title'), album.get('mediaItemsCount'))
        message(text)

        # TODO BACKUP
        s3 = boto3.resource('s3')
        for bucket in s3.buckets.all():
            message(bucket.name)


    except Exception as e:
        err = e.with_traceback(sys.exc_info()[2])
        errtext = 'error: {0}({1})'.format(err.__class__.__name__, str(err))
        try:
            message(errtext)
        except Exception as e:
            err = e.with_traceback(sys.exc_info()[2])
            errtext = 'error: {0}({1})'.format(err.__class__.__name__, str(err))
            print(errtext, file=sys.stderr)

