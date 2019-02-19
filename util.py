from datetime import datetime, timezone, timedelta
import os
import sys

def environ(keys, header):
    ret = False
    for k in keys:
        if os.environ.get(k) is None:
            ret = True
            print('{0}: {1} is not set'.format(header, k), file=sys.stderr)
    return ret

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

