from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import TokenExpiredError
import os
import time

class Credential():
    def __init__(self, out, oauth_client, oauth_secret, token_url, scope, redirect_url, authorization_base_url, token=None, refresh_url=None, email=None):
        self.out = out
        self.token = token
        self.token_url = token_url
        self.refresh_url = refresh_url
        self.email = email
        self.oauth_client = oauth_client
        self.oauth_secret = oauth_secret
        self.scope = scope
        self.redirect_url = redirect_url
        self.authorization_base_url = authorization_base_url
        self.authorization_state = None
        self.redirect_response = None

    def authorization_step(self):
        google = OAuth2Session(self.oauth_client, scope=self.scope, redirect_uri=self.redirect_url)
        authorization_url, self.authorization_state = \
            google.authorization_url(
                self.authorization_base_url,
                access_type="offline",
                prompt="select_account")
        return authorization_url

    def fetch_token(self):
        # wait 5 minutes
        count = 0
        while count < 60 * 5:
            if self.redirect_response is not None:
                break
            time.sleep(1)
            count += 1
        if self.redirect_response is None:
            raise RuntimeError('timed out')
        google = OAuth2Session(self.oauth_client, scope=self.scope, redirect_uri=self.redirect_url)
        self.token = google.fetch_token(
            self.token_url, client_secret=self.oauth_secret,
            authorization_response=self.redirect_response)
        self.get_email()

    def get_email(self):
        userinfo = self.get('https://people.googleapis.com/v1/people/me?personFields=emailAddresses')
        self.email = None
        for i in userinfo.get('emailAddresses'):
            if i.get('metadata').get('primary') == True:
                self.email = i.get('value')
                break
        if self.email is None:
            raise RuntimeError('error: cannot find primary email address.')
        return self.email

    def get(self, url, *, params=None):
        r = None
        ret = None
        try:
            google = OAuth2Session(os.environ.get('GOOGLE_OAUTH_CLIENT'), token=self.token)
            r = google.get(url, params=params)
        except TokenExpiredError as e:
            extra = {
                'client_id': os.environ.get('GOOGLE_OAUTH_CLIENT'),
                'client_secret': os.environ.get('GOOGLE_OAUTH_SECRET')
            }
            self.out.info('raised TokenExpiredError, refresh token. refresh_url={}'.format(self.refresh_url))
            try:
                token = google.refresh_token(self.refresh_url, **extra)
            except Exception as e:
                self.out.exception('failed to refresh token', e)
                raise

            r = google.get(url, params=params)
        r.raise_for_status()
        ret = r.json()
        return ret

    def post(self, url, *, data=None):
        if data is None:
            raise RuntimeError('post() data param must be set')
        r = None
        ret = None
        try:
            google = OAuth2Session(os.environ.get('GOOGLE_OAUTH_CLIENT'), token=self.token)
            r = google.post(url, data=data)
        except TokenExpiredError as e:
            extra = {
                'client_id': os.environ.get('GOOGLE_OAUTH_CLIENT'),
                'client_secret': os.environ.get('GOOGLE_OAUTH_SECRET')
            }
            self.out.info('raised TokenExpiredError, refresh token. refresh_url={}'.format(self.refresh_url))
            try:
                token = google.refresh_token(self.refresh_url, **extra)
            except Exception as e:
                self.out.exception('failed to refresh token', e)
                raise

            r = google.get(url, data=data)
        r.raise_for_status()
        ret = r.json()
        return ret
