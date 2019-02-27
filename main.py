import sys
import logging
import schedule
import asyncio
import time
import os
from datetime import datetime
import threading
import socket

import util
import callback
import backup
import credential

callback_url = '/callback'
authorization_base_url = "https://accounts.google.com/o/oauth2/v2/auth"
token_url = "https://www.googleapis.com/oauth2/v4/token"
scope = ['https://www.googleapis.com/auth/photoslibrary.readonly',
         'https://www.googleapis.com/auth/userinfo.profile',
         'https://www.googleapis.com/auth/userinfo.email']
basedir = '/data/photod'
logdir = '/logs/photod'

class Scheduler():
    def __init__(self, loop, out, backup):
        self.loop = loop
        self.out = out
        self.backup = backup

    def run(self):
        try:
            if self.loop is None:
                self.out.debug('launch scheduler as current thread')
            else:
                asyncio.set_event_loop(self.loop)
                self.out.debug('launch scheduler as new thread')
            schedule.every().day.at(os.environ.get('SCHEDULE')).do(self.backup.run)
            while True:
                schedule.run_pending()
                time.sleep(1)
        except Exception as e:
            self.out.exception('error: scheduler', e)

if __name__ == '__main__':
    envse = ['GOOGLE_OAUTH_CLIENT', 'GOOGLE_OAUTH_SECRET', 'DISCORDBOT', 'BASE_URL',
             'S3_BUCKET', 'S3_PREFIX', 'SCHEDULE']

    f = util.environ(envse, 'error')

    out = util.Output(logdir)
    if f:
        out.error('error: some environment variables are not set. exiting.')
        sys.exit(1)

    os.makedirs(basedir, exist_ok=True)

    try:
        redirect_url = '{0}{1}'.format(os.environ['BASE_URL'], callback_url)
        cred = credential.Credential(out,
            os.environ['GOOGLE_OAUTH_CLIENT'], os.environ['GOOGLE_OAUTH_SECRET'],
            token_url, scope, redirect_url, authorization_base_url)
        out.info('listen at {0}'.format(socket.gethostbyname_ex(socket.gethostname())))
        cb = callback.Callback(asyncio.new_event_loop(), out, cred, callback_url)
        threading.Thread(target=cb.run, name='callback', daemon=True).start()
        #httploop = asyncio.new_event_loop()
        #threading.Thread(target=httpserver, args=(httploop,)).start()

        back = backup.Backup(out, cb, cred, os.environ['S3_BUCKET'], os.environ['S3_PREFIX'], basedir)

        back.authorize(authorization_base_url, token_url,
                       scope,
                       os.environ['GOOGLE_OAUTH_CLIENT'],
                       os.environ['GOOGLE_OAUTH_SECRET'],
                       os.environ['BASE_URL'],
                       callback_url)

        if os.environ.get('ONESHOT') is None:
            #sched = Scheduler(asyncio.new_event_loop(), out, back)
            #threading.Thread(target=sched.run, name='scheduler', daemon=True).start()
            sched = Scheduler(None, out, back)            
            sched.run()
        # logger.debug('authorized. token={0}'.format(token))
        
        if os.environ.get('ONESHOT') is not None:
            back.run()
    except Exception as e:
        out.exception('error: main', e)
