import os
import sys
import time
import boto3
import requests

import util

class Albums():
    def __init__(self, out, starttime, catalogdir, credential, bucketname, bucketprefix):
        self.out = out
        self.starttime = starttime
        self.catalogdir = catalogdir
        self.credential = credential

        s3 = boto3.resource('s3')
        self.bucket = s3.Bucket(bucketname)
        self.bucketprefix = bucketprefix

    def album_catalog(self, id, name):
        os.makedirs('{0}/catalog/{1}'.format(self.catalogdir, self.starttime), exist_ok=True)
        cat = open('{0}/catalog/{1}/album'.format(self.catalogdir, self.starttime), 'a', encoding='utf-8')
        cat.write('{0} {1}\n'.format(id, name))
        cat.close()

    def photo_catalog(self, albumid, id, name):
        os.makedirs('{0}/catalog/{1}/albums'.format(self.catalogdir, self.starttime), exist_ok=True)
        cat = open('{0}/catalog/{1}/albums/{2}'.format(self.catalogdir, self.starttime, albumid), 'a', encoding='utf-8')
        cat.write('{0} {1}\n'.format(id, name))
        cat.close()

    def put_album_catalog(self, bucket, prefix):
        cat = open('{0}/catalog/{1}/album'.format(self.catalogdir, self.starttime), 'rb')
        bucket.Object(prefix).put(Body=cat)
        cat.close()

    def put_photo_catalog(self, bucket, prefix, albumid):
        cat = open('{0}/catalog/{1}/albums/{2}'.format(self.catalogdir, self.starttime, albumid), 'rb')
        bucket.Object(prefix).put(Body=cat)
        cat.close()

    def put_photos(self, r, rp, already_saved,
                album_current, album_count, photo_current, photo_count, album, item, prefix):
        src = '{0}{1}'.format(item.get('baseUrl'), '=w10000-h10000')
        dest = prefix + item.get('id')
        if dest in already_saved:
            # debug
            self.out.debug('{0}/{1}-{2}/{3}: already exists:{4} {5}'.format(
                album_current + 1, album_count,
                photo_current + 1, photo_count,
                item.get('filename'), item.get('id')))
            return 3
        else:
            # debug
            self.out.debug('{}/{}-{}/{}: uploading photo: {} {}'.format(
                album_current + 1, album_count,
                photo_current + 1, photo_count,
                item.get('filename'), item.get('id')))
            imageres = requests.get(src)
            if imageres.status_code != 200:
                # retry
                time.sleep(5)
                imageres = requests.get('{0}{1}'.format(item.get('baseUrl'), '=w10000-h10000'))
                if imageres.status_code != 200:
                    self.out.error('error {0} at {1}/{2}-{3}/{4}: {5} {6}\n'.format(
                        imageres.status_code,
                        album_current + 1, album_count,
                        photo_current + 1, photo_count,
                        item.get('filename'), src))
                    #failureCount += 1
                    return 1

            try:
                self.bucket.Object(dest).put(Body=imageres.content)
            except Exception as e:
                err = 'error at {}/{}-{}/{}: {} {}'.format(
                    album_current + 1, album_count,
                    photo_current + 1, photo_count,
                    item.get('filename'), src)
                self.out.exception(err, e)
                return 2
        return 0

    def put_albums(self, r, album_current, album_count, album):
        success_count = 0
        failure_count = 0
        already_count = 0
        photo_current = 0
        photo_count = 0

        prefix = os.path.join(self.bucketprefix, self.credential.email, album.get('id')) + '/'
        self.out.debug('prefix: {0}'.format(prefix))

        already_saved = [ o.key for o in self.bucket.objects.filter(Prefix=prefix)]

        if len(already_saved) > 0:
            self.out.debug('{0}/{1}: already exists: {2} photos found. first record={3}'.format(
                album_current, album_count, len(already_saved), already_saved[0]))
        else:
            self.out.debug('{0}/{1}: not found that already saved photo'.format(
                        album_current, album_count))

        self.album_catalog(album.get('id'), album.get('title'))

        rp = None
        page = 0
        while rp is None or rp.get('nextPageToken') is not None:
            if rp is None:
                rp = self.credential.post('https://photoslibrary.googleapis.com/v1/mediaItems:search',
                                data={ 'pageSize': 100, 'albumId': album.get('id') })
            else:
                rp = self.credential.post('https://photoslibrary.googleapis.com/v1/mediaItems:search',
                                data={ 'pageSize': 100, 'albumId': album.get('id'),
                                       'pageToken': rp.get('nextPageToken') })
            photo_count += len(rp.get('mediaItems'))
            failure_per_page = 0
            for item in rp.get('mediaItems'):
                ret = self.put_photos(r, rp, already_saved,
                                album_current, album_count, photo_current, photo_count,
                                album, item, prefix)
                if ret == 0:
                    success_count += 1
                    self.photo_catalog(album.get('id'), item.get('id'), item.get('filename'))
                elif ret == 1:
                    failure_count += 1
                    failure_per_page += 1
                elif ret == 2:
                    failure_count += 1
                    failure_per_page += 1
                elif ret == 3:
                    already_count += 1
                    self.photo_catalog(album.get('id'), item.get('id'), item.get('filename'))
                photo_current += 1
            self.out.debug('{}/{}-{}: count: {}, failure photos: {}'.format(
                        album_current, album_count, page + 1, len(rp.get('mediaItems')), failure_per_page))
            page += 1

        catalog_prefix = os.path.join(self.bucketprefix, self.credential.email, 'catalog', 'albums', album.get('id'))
        self.out.debug('{0}/{1}: put photo catalog to={2}'.format(
                    album_current, album_count, catalog_prefix))
        self.put_photo_catalog(self.bucket, catalog_prefix, album.get('id'))

        ret = 0
        emoji = ''
        if int(album.get('mediaItemsCount')) == success_count + already_count:
            ret = 0
            emoji = 'ok'
        else:
            ret = 1
            emoji = 'bad'
        self.out.put('{0} {1}/{2} album {3}: total {4}, success {5}, already {6}, failure {7}'.format(
            util.emoji(emoji), album_current + 1, album_count, album.get('title'),
            album.get('mediaItemsCount'), success_count, already_count, failure_count))
        return ret

    def run(self):
        success_albums = 0
        failure_albums = 0
        album_current = 0
        album_count = 0
        r = None
        page = 0
        while r is None or r.get('nextPageToken') is not None:
            if r is None:
                r = self.credential.get('https://photoslibrary.googleapis.com/v1/albums')
            else:
                r = self.credential.get('https://photoslibrary.googleapis.com/v1/albums',
                        params={'pageToken': r.get('nextPageToken')})
            # albums may not return values
            if r.get('albums') is None:
                continue
            album_count += len(r.get('albums'))
            self.out.put('Albums.run(): {0} albums found in this page, nextPageToken={1}\n'.format(
                len(r.get('albums')), r.get('nextPageToken')))

            for album in r.get('albums'):
                ret = self.put_albums(r, album_current, album_count, album)
                ret = 0
                if ret == 0:
                    success_albums += 1
                else:
                    failure_albums += 1
                album_current += 1
            page += 1

        catalog_prefix = os.path.join(self.bucketprefix, self.credential.email, 'catalog', 'album')
        self.out.debug('put album catalog to={0}'.format(catalog_prefix))
        self.put_album_catalog(self.bucket, catalog_prefix)

        success_all = False
        emoji = ''
        if album_count == success_albums:
            emoji = 'ok'
            success_all = True
        else:
            emoji = 'bad'
        self.out.message('{0} finished: total {1}, success {2}, failure {3}\n'.format(
            util.emoji(emoji), album_count, success_albums, failure_albums))
        if success_all == False:
            self.out.pop()
