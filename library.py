import os
import sys
import time
import boto3
import requests

import util

class Library():
    def __init__(self, out, starttime, basedir, credential, bucketname, bucketprefix):
        self.out = out
        self.starttime = starttime
        self.basedir = basedir
        self.credential = credential

        s3 = boto3.resource('s3')
        self.bucket = s3.Bucket(bucketname)
        self.bucketprefix = bucketprefix


    def photo_catalog(self, id, name):
        os.makedirs('{0}/catalog/{1}/albums'.format(self.basedir, self.starttime), exist_ok=True)
        cat = open('{0}/catalog/{1}/albums/{2}'.format(self.basedir, self.starttime, 'library'), 'a', encoding='utf-8')
        cat.write('{0} {1}\n'.format(id, name))
        cat.close()

    def put_photo_catalog(self, prefix):
        cat = open('{0}/catalog/{1}/albums/{2}'.format(self.basedir, self.starttime, 'library'), 'rb')
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
                    #failureCount += 1
                    return 1

            try:
                self.bucket.Object(dest).put(Body=imageres.content)
            except Exception as e:
                err = e.with_traceback(sys.exc_info()[2])
                err = 'put_photos(): error at library-{}-{}/{}: {}'.format(
                    page, current + 1, count, item.get('filename'))
                self.out.exception(err, e)
                #failureCount += 1
                return 2

            # uploaded a photo
            #successCount += 1
        #photoCurrent += 1
        return 0


    def run(self):
        page = 0
        count = 0
        current = 0
        success = 0
        failure = 0
        already = 0
        skip = 0

        prefix = '/'.join([os.environ.get('S3_PREFIX'), self.credential.email, 'library', ''])
        self.out.debug('prefix: {0}'.format(prefix))
        already_saved = [ o.key for o in self.bucket.objects.filter(Prefix=prefix)]

        r = self.credential.get('https://photoslibrary.googleapis.com/v1/mediaItems',
                        params={ 'pageSize': 100 })
        count += len(r.get('mediaItems'))
        self.out.debug('library-1: nextPageToken={}'.format(r.get('nextPageToken') is not None))
        for item in r.get('mediaItems'):
            ret = self.put_photos(r, already_saved, current, count, item, prefix)
            if ret == 0:
                success += 1
                self.photo_catalog(item.get('id'), item.get('filename'))
            elif ret == 1:
                failure += 1
            elif ret == 2:
                failure += 1
            elif ret == 3:
                already += 1
                self.photo_catalog(item.get('id'), item.get('filename'))
            current += 1

        while r.get('nextPageToken') is not None:
            # debug
            self.out.debug('library-{}: nextPageToken found'.format(page + 1))
            r = self.credential.get('https://photoslibrary.googleapis.com/v1/mediaItems',
                        params={ 'pageSize': '100',
                                    'pageToken': r.get('nextPageToken') })
            count += len(r.get('mediaItems'))
            for item in r.get('mediaItems'):
                ret = self.put_photos(r, already_saved, page, current, count, item, prefix)
                if ret == 0:
                    success += 1
                    self.photo_catalog(item.get('id'), item.get('filename'))
                elif ret == 1:
                    failure += 1
                elif ret == 2:
                    failure += 1
                elif ret == 3:
                    already += 1
                    self.photo_catalog(item.get('id'), item.get('filename'))
                current += 1
            page += 1

        catalog_prefix = '/'.join([os.environ.get('S3_PREFIX'), self.credential.email, 'catalog', 'library'])
        #catalog_prefix = os.environ.get('S3_PREFIX') + '/' + email + '/catalog/albums/' + album.get('id')
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
