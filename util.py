from datetime import datetime, timezone, timedelta
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import TokenExpiredError
import os
import sys
import logging
import requests
import json

def environ(keys, header):
    ret = False
    for k in keys:
        if os.environ.get(k) is None:
            ret = True
            print('{0}: {1} is not set'.format(header, k), file=sys.stderr)
    return ret

def environ_bool(key):
    v = os.environ.get(key)
    if v is None:
        return False
    v = v.lower()
    return v != "0" and v != "false" and v != "no"
        
def emoji(name):
    if name == 'ok':
        return ':white_check_mark:'
    elif name == 'bad':
        return ':red_circle:'
    else:
        return 'emoji not defined'

def unixtimestr(ut):
    return datetime.fromtimestamp(
        ut, timezone(timedelta(hours=+9), 'JST')).strftime('%m/%d %H:%M')

def unixtimestrt(ut):
    return datetime.fromtimestamp(
        ut, timezone(timedelta(hours=+9), 'JST')).strftime('%H:%M')


class Output():
    def __init__(self, logdir, debug):
        self._array = []
        os.makedirs(logdir, exist_ok=True)
        self.starttime = datetime.now().strftime('%Y%m%d-%H%M')
        logging.getLogger().setLevel(logging.WARNING)
        self.logger = logging.getLogger('photod')
        if debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
        logFormatter = logging.Formatter(fmt='%(asctime)s %(levelname)s: %(message)s',
                                        datefmt='%Y%m%d-%H%M')
        fileHandler = logging.FileHandler('/{}/{}'.format(logdir, self.starttime))
        fileHandler.setFormatter(logFormatter)
        self.logger.addHandler(fileHandler)
        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(logFormatter)
        self.logger.addHandler(consoleHandler)

        self.info('started photod at {0}'.format(self.starttime))

    def message(self, data):
        if type(data) is str:
            data = { 'message': data }
        self.info('message: {}'.format(data.get('message')))
        if data.get('message') is not None:
            data['message'] = 'photod: ' + data['message']
        try:
            r = requests.post('http://' + os.environ.get('DISCORDBOT'),
                            data=json.dumps(data).encode('utf-8'),
                            headers={'content-type': 'application/json'})
            if r.status_code != 200:
                self.error('failure to send message to discordbot, status={0}'.format(r.status_code))
        except Exception as e:
            self.exception('message() error', e)

    def put(self, data):
        self.info(data)
        self._array.append(data)

    def pop(self):
        if len(self._array) > 0:
            self.message('\n'.join(self._array))
            self._array.clear()

    def debug(self, msg):
        self.logger.debug(msg)
    
    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)
        self.message(msg)

    def exception(self, msg, err):
        self.logger.exception(msg, stack_info=True)
        self.message('{}: {}({})'.format(msg, err.__class__.__name__, str(err)))
