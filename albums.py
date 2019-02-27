import os
import sys
import time
import boto3
import requests

import util

class Albums():
    def __init__(self, out, starttime, basedir, credential, bucketname, bucketprefix):
        self.out = out
        self.starttime = starttime
        self.basedir = basedir
        self.credential = credential

        s3 = boto3.resource('s3')
        self.bucket = s3.Bucket(bucketname)
        self.bucketprefix = bucketprefix

    def album_catalog(self, id, name):
        os.makedirs('{0}/catalog/{1}'.format(self.basedir, self.starttime), exist_ok=True)
        cat = open('{0}/catalog/{1}/album'.format(self.basedir, self.starttime), 'a', encoding='utf-8')
        cat.write('{0} {1}\n'.format(id, name))
        cat.close()

    def photo_catalog(self, albumid, id, name):
        os.makedirs('{0}/catalog/{1}/albums'.format(self.basedir, self.starttime), exist_ok=True)
        cat = open('{0}/catalog/{1}/albums/{2}'.format(self.basedir, self.starttime, albumid), 'a', encoding='utf-8')
        cat.write('{0} {1}\n'.format(id, name))
        cat.close()

    def put_album_catalog(self, bucket, prefix):
        cat = open('{0}/catalog/{1}/album'.format(self.basedir, self.starttime), 'rb')
        bucket.Object(prefix).put(Body=cat)
        cat.close()

    def put_photo_catalog(self, bucket, prefix, albumid):
        cat = open('{0}/catalog/{1}/albums/{2}'.format(self.basedir, self.starttime, albumid), 'rb')
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
                err = e.with_traceback(sys.exc_info()[2])
                err = 'error {0} at {1}/{2}-{3}/{4}: {5} {6} ({7})'.format(
                    err.__class__.__name__,
                    album_current + 1, album_count,
                    photo_current + 1, photo_count,
                    item.get('filename'), src, str(err))
                self.out.exception(err, e)
                #failureCount += 1
                return 2

            # uploaded a photo
            #success_count += 1
        #photo_current += 1
        return 0

    def put_albums(self, r, albumCurrent, albumCount, album):
        #message('{0}/{1} {2}: {3} items\n'.format(
        #    albumCurrent + 1, len(r.get('albums')), album.get('title'), album.get('mediaItemsCount')))
        success_count = 0
        failure_count = 0
        already_count = 0
        photo_current = 0
        photo_count = 0

        #for bucket in s3.buckets.all():
        #    message(bucket.name)
        prefix = '/'.join([self.bucketprefix, self.credential.email, album.get('id'), ''])
        self.out.debug('prefix: {0}'.format(prefix))
        #l = bucket.objects.filter(Prefix=prefix)
        already_saved = [ o.key for o in self.bucket.objects.filter(Prefix=prefix)]
        # s3 pagenation has not implemented yet
        #logger.debug('{0}'.format(l))

        #already_saved = []
        #if l is not None and 'Contents' in l:
        #    already_saved = [content['Key'] for content in l['Contents']]
        if len(already_saved) > 0:
            self.out.debug('{0}/{1}: already exists: {2} photos found. first record={3}'.format(
                albumCurrent, albumCount, len(already_saved), already_saved[0]))
        else:
            self.out.debug('{0}/{1}: not found that already saved photo'.format(
                        albumCurrent, albumCount))

        # append (album id, album name) pair to albumcat
        self.album_catalog(album.get('id'), album.get('title'))

        rp = self.credential.post('https://photoslibrary.googleapis.com/v1/mediaItems:search',
                        data={ 'pageSize': 100, 'albumId': album.get('id') })
        photo_count += len(rp.get('mediaItems'))
        self.out.debug('{0}/{1}: nextPageToken={2}'.format(
            albumCurrent, len(r.get('albums')), rp.get('nextPageToken') is not None))
        for item in rp.get('mediaItems'):
            ret = self.put_photos(r, rp, already_saved,
                            albumCurrent, albumCount, photo_current, photo_count,
                            album, item, prefix)
            if ret == 0:
                success_count += 1
                self.photo_catalog(album.get('id'), item.get('id'), item.get('filename'))
            elif ret == 1:
                failure_count += 1
            elif ret == 2:
                failure_count += 1
            elif ret == 3:
                already_count += 1
                self.photo_catalog(album.get('id'), item.get('id'), item.get('filename'))
            photo_current += 1

        while rp.get('nextPageToken') is not None:
            # debug
            self.out.debug('{0}/{1}: put_albums(): nextPageToken found in current album'.format(
                        albumCurrent, albumCount))
            rp = self.credential.post('https://photoslibrary.googleapis.com/v1/mediaItems:search',
                                data={ 'pageSize': 100, 'albumId': album.get('id'),
                                    'pageToken': rp.get('nextPageToken')        })
            photo_count += len(rp.get('mediaItems'))
            for item in rp.get('mediaItems'):
                ret = self.put_photos(r, rp, already_saved,
                                albumCurrent, albumCount, photo_current, photo_count,
                                album, item, prefix)
                if ret == 0:
                    success_count += 1
                    self.photo_catalog(album.get('id'), item.get('id'), item.get('filename'))
                elif ret == 1:
                    failure_count += 1
                elif ret == 2:
                    failure_count += 1
                elif ret == 3:
                    already_count += 1
                    self.photo_catalog(album.get('id'), item.get('id'), item.get('filename'))
                photo_current += 1

        catalog_prefix = '/'.join([self.bucketprefix, self.credential.email, 'catalog', 'albums', album.get('id')])
        #catalog_prefix = self.bucketprefix + '/' + credential.email + '/catalog/albums/' + album.get('id')
        self.out.debug('{0}/{1}: put photo catalog to={2}'.format(
                    albumCurrent, albumCount, catalog_prefix))
        self.put_photo_catalog(self.bucket, catalog_prefix, album.get('id'))

        ret = 0
        emoji = ''
        if int(album.get('mediaItemsCount')) == success_count + already_count:
            #successAlbums += 1
            ret = 0
            emoji = 'ok'
        else:
            #failureAlbums += 1
            ret = 1
            emoji = 'bad'
        self.out.put('{0} {1}/{2} album {3}: total {4}, success {5}, already {6}, failure {7}\n'.format(
            util.emoji(emoji), albumCurrent + 1, albumCount, album.get('title'),
            album.get('mediaItemsCount'), success_count, already_count, failure_count))
        #albumCurrent += 1
        return ret

    def run(self):
        success_albums = 0
        failure_albums = 0
        album_current = 0
        album_count = 0

        self.out.debug('opening s3')

        r = self.credential.get('https://photoslibrary.googleapis.com/v1/albums')
        album_count += len(r.get('albums'))
        self.out.put('{0} albums found in this page, nextPageToken={1}\n'.format(
            len(r.get('albums')), r.get('nextPageToken') is not None))


        for album in r.get('albums'):
            ret = self.put_albums(r, album_current, album_count, album)
            if ret == 0:
                success_albums += 1
            else:
                failure_albums += 1
            album_current += 1

        while r.get('nextPageToken') is not None:
            r = self.credential.get('https://photoslibrary.googleapis.com/v1/albums')
            album_count += len(r.get('albums'))
            self.out.put('{0} albums found in this page, nextPageToken={1}\n'.format(
                len(r.get('albums')),
                 r.get('nextPageToken') is not None))

            for album in r.get('albums'):
                ret = self.put_albums(r, album_current, album_count, album)
                if ret == 0:
                    success_albums += 1
                else:
                    failure_albums += 1
                album_current += 1

        catalog_prefix = '/'.join([self.bucketprefix, self.credential.email, 'catalog', 'album'])
        self.out.debug('put album catalog to={0}'.format(catalog_prefix))
        self.put_album_catalog(self.bucket, catalog_prefix)

        success_all = False
        emoji = ''
        if len(r.get('albums')) == success_albums:
            emoji = 'ok'
            success_all = True
        else:
            emoji = 'bad'
        self.out.message('{0} finished: total {1}, success {2}, failure {3}\n'.format(
            util.emoji(emoji), len(r.get('albums')), success_albums, failure_albums))
        if success_all == False:
            self.out.pop()
