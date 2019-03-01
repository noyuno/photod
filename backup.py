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

    def run(self):
        starttime = datetime.now().strftime('%Y%m%d-%H%M')
       
        alb = albums.Albums(self.out, starttime, self.basedir, self.credential, self.bucketname, self.bucketprefix)
        alb.run()
        lib = library.Library(self.out, starttime, self.basedir, self.credential, self.bucketname, self.bucketprefix)
        lib.run()
