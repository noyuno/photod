import os
import sys
import time
import boto3
import requests

import util

class Library():
    def __init__(self, out, starttime, catalogdir, credential, bucketname, bucketprefix):
        self.out = out
        self.starttime = starttime
        self.catalogdir = catalogdir
        self.credential = credential

        s3 = boto3.resource('s3')
        self.bucket = s3.Bucket(bucketname)
        self.bucketprefix = bucketprefix

    def photo_catalog(self, id, name):
        os.makedirs('{0}/catalog/{1}/albums'.format(self.catalogdir, self.starttime), exist_ok=True)
        cat = open('{0}/catalog/{1}/albums/{2}'.format(self.catalogdir, self.starttime, 'library'), 'a', encoding='utf-8')
        cat.write('{0} {1}\n'.format(id, name))
        cat.close()

    def put_photo_catalog(self, prefix):
        cat = open('{0}/catalog/{1}/albums/{2}'.format(self.catalogdir, self.starttime, 'library'), 'rb')
        self.bucket.Object(prefix).put(Body=cat)
        cat.close()


    def put_photos(self, r, already_saved, page, current, count, item, prefix):
        src = '{0}{1}'.format(item.get('baseUrl'), '=w10000-h10000')
        dest = prefix + item.get('id')
        if dest in already_saved:
            # debug
            self.out.debug('library-{}-{}/{}: already exists:{} {}'.format(
                page, current + 1, count, item.get('filename'), item.get('id')))
            return 3
        else:
            # debug
            self.out.debug('library-{}-{}/{}: uploading photo: {} {}'.format(
                page, current + 1, count, item.get('filename'), item.get('id')))
            imageres = requests.get(src)
            if imageres.status_code != 200:
                # retry
                time.sleep(5)
                imageres = requests.get('{0}{1}'.format(item.get('baseUrl'), '=w10000-h10000'))
                if imageres.status_code != 200:
                    self.out.error('error {} at library-{}-{}/{}: {} {}\n'.format(
                        imageres.status_code, page, current + 1, count, item.get('filename'), src))
                    return 1

            try:
                self.bucket.Object(dest).put(Body=imageres.content)
            except Exception as e:
                err = 'put_photos(): error at library-{}-{}/{}: {}'.format(
                    page, current + 1, count, item.get('filename'))
                self.out.exception(err, e)
                return 2
        return 0


    def run(self):
        page = 0
        count = 0
        current = 0
        success = 0
        failure = 0
        already = 0
        skip = 0

        prefix = os.path.join(os.environ.get('S3_PREFIX'), self.credential.email, 'library', '')
        self.out.debug('prefix: {0}'.format(prefix))
        already_saved = [ o.key for o in self.bucket.objects.filter(Prefix=prefix)]

        r = None
        while r is None or r.get('nextPageToken') is not None:
            if r is None:
                r = self.credential.get('https://photoslibrary.googleapis.com/v1/mediaItems',
                        params={ 'pageSize': '100' })
            else:
                r = self.credential.get('https://photoslibrary.googleapis.com/v1/mediaItems',
                        params={ 'pageSize': '100',
                                 'pageToken': r.get('nextPageToken')})
            # mediaItems may not return values
            if r.get('mediaItems') is None:
                continue
            count += len(r.get('mediaItems'))
            failure_per_page = 0
            for item in r.get('mediaItems'):
                ret = self.put_photos(r, already_saved, page, current, count, item, prefix)
                if ret == 0:
                    success += 1
                    self.photo_catalog(item.get('id'), item.get('filename'))
                elif ret == 1:
                    failure += 1
                    failure_per_page += 1
                elif ret == 2:
                    failure += 1
                    failure_per_page += 1
                elif ret == 3:
                    already += 1
                    self.photo_catalog(item.get('id'), item.get('filename'))
                current += 1
            self.out.info('library-{}: count: {}, failure photos: {}'.format(page + 1, len(r.get('mediaItems')), failure_per_page))
            page += 1

        catalog_prefix = os.path.join(os.environ.get('S3_PREFIX'), self.credential.email, 'catalog', 'library')
        self.out.debug('library: put catalog to={}'.format(catalog_prefix))
        self.put_photo_catalog(catalog_prefix)

        success_all = False
        emoji = ''
        if count == success + already:
            success_all = True
            emoji = 'ok'
        else:
            emoji = 'bad'
        self.out.message('{}library: total {}, success {}, already {}, failure {}\n'.format(
            util.emoji(emoji), count, success, already, failure))
        if success_all == False:
            self.out.pop()
