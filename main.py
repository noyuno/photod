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
tokendir = '/data/photod/token'
catalogdir = '/logs/photod/catalog'
logdir = '/logs/photod/log'

class Scheduler():
    def __init__(self, loop, out, backup):
        self.loop = loop
        self.out = out
        self.backup = backup

    def run(self):
        try:
            if self.loop is None:
                self.out.debug('launch scheduler in current thread')
            else:
                asyncio.set_event_loop(self.loop)
                self.out.debug('launch scheduler in new thread')
            weekdays = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
            for w in os.environ.get('SCHEDULE_WEEKDAY').split(','):
                eval('schedule.every().{}.at(\'{}\').do(self.backup.run)'.format(weekdays[int(w)], os.environ.get('SCHEDULE_TIME')))
            while True:
                schedule.run_pending()
                time.sleep(1)
        except Exception as e:
            self.out.exception('error: scheduler', e)

def main():
    envse = ['GOOGLE_OAUTH_CLIENT', 'GOOGLE_OAUTH_SECRET', 'DISCORDBOT', 'BASE_URL',
             'S3_BUCKET', 'S3_PREFIX']

    out = util.Output(logdir, util.environ_bool('DEBUG'))
    f = util.environ(envse, 'error')
    if f:
        out.error('error: some environment variables are not set. exiting.')
        sys.exit(1)
    if os.environ.get('ONESHOT') is None and (os.environ.get('SCHEDULE_TIME') is None or os.environ.get('SCHEDULE_WEEKDAY') is None):
        out.error('error: environment variables ONESHOT or (SCHEDULE_TIME and SCHEDULE_WEEKDAY) must be set. exiting.')
        sys.exit(1)

    os.makedirs(catalogdir, exist_ok=True)

    try:
        redirect_url = '{0}{1}'.format(os.environ['BASE_URL'], callback_url)
        cred = credential.Credential(out,
            os.environ['GOOGLE_OAUTH_CLIENT'], os.environ['GOOGLE_OAUTH_SECRET'],
            token_url, scope, redirect_url, authorization_base_url, tokendir)
        cb = callback.Callback(asyncio.new_event_loop(), out, cred, callback_url)
        threading.Thread(target=cb.run, name='callback', daemon=True).start()

        album = util.environ_bool('ALBUM')
        library = util.environ_bool('LIBRARY')
        back = backup.Backup(out, cb, cred, os.environ['S3_BUCKET'], os.environ['S3_PREFIX'], catalogdir, album, library)

        if cred.load():
            out.info('using saved token')
        else:
            authorization_url = cred.authorization_step()
            out.message('Please authenticate the application: {0}'.format(authorization_url))
            cred.wait_authorization()
            out.info('main(): authorized, email={}'.format(cred.email))

        if util.environ_bool('ONESHOT'):
            back.run()
            out.info('main(): all tasks done')
        else:
            sched = Scheduler(None, out, back)            
            sched.run()
            out.error('main(): scheduler down!')
    except Exception as e:
        out.exception('error: main', e)

if __name__ == '__main__':
    main()
