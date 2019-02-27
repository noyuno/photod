import os
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import TokenExpiredError
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
from datetime import datetime, timezone, timedelta

import util
import library
import albums

class Backup():
    def __init__(self, out, callback, credential, bucketname, bucketprefix, basedir):
        self.out = out
        self.queued_message = []
        self.callback = callback
        self.credential = credential
        self.bucketname = bucketname
        self.bucketprefix = bucketprefix
        self.basedir = basedir

    def authorize(self, authorization_base_url, token_url, scope, oauth_client, oauth_secret, baseurl, callback_url):
        #redirect_url = '{0}{1}'.format(baseurl, callback_url)
        #google = OAuth2Session(oauth_client, scope=scope, redirect_uri=redirect_url)
        #authorization_url, self.callback.authorization_state = \
        #    google.authorization_url(
        #        authorization_base_url,
        #        access_type="offline",
        #        prompt="select_account")
        authorization_url = self.credential.authorization_step()
        self.out.message('Please authenticate the application: {0}'.format(authorization_url))

        self.credential.fetch_token()
        #self.credential.token = google.fetch_token(token_url,
        #                           client_secret=oauth_secret, #os.environ.get('GOOGLE_OAUTH_SECRET'),
        #                           authorization_response=self.callback.redirect_response)

    def run(self):
        starttime = datetime.now().strftime('%Y%m%d-%H%M')
       
        alb = albums.Albums(self.out, starttime, self.basedir, self.credential, self.bucketname, self.bucketprefix)
        alb.run()
        lib = library.Library(self.out, starttime, self.basedir, self.credential, self.bucketname, self.bucketprefix)
        lib.run()
        self.out.info('backup.run(): all tasks done')
