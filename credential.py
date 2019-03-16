from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import TokenExpiredError
import os
import time
import json

class Credential():
    def __init__(self, out, oauth_client, oauth_secret, token_url, scope, redirect_url, authorization_base_url, tokendir):
        self.out = out
        self.token_url = token_url
        self.oauth_client = oauth_client
        self.oauth_secret = oauth_secret
        self.scope = scope
        self.redirect_url = redirect_url
        self.tokendir = tokendir
        self.authorization_base_url = authorization_base_url
        self.authorization_state = None
        self.redirect_response = None
        self.token = None
        self.email = None
        self.extra = {
            'client_id': self.oauth_client,
            'client_secret': self.oauth_secret
        }

    def authorization_step(self):
        google = OAuth2Session(self.oauth_client, scope=self.scope, redirect_uri=self.redirect_url)
        # prompt="consent": https://github.com/googleapis/google-api-python-client/issues/213#issuecomment-205886341
        authorization_url, self.authorization_state = \
            google.authorization_url(
                self.authorization_base_url,
                access_type="offline",
                prompt="consent")
        return authorization_url

    def load(self):
        token_path = os.path.join(self.tokendir, 'token')
        if os.path.exists(token_path):
            with open(token_path, 'r') as fp:            
                self.token = json.load(fp)
            self.get_email()
            return True
        return False

    def save_token(self, token):
        # check refreshable token
        if token.get('refresh_token') is None:
            raise RuntimeError('This token is not refreshable. refresh_token not found.')
        path = os.path.join(self.tokendir, 'token')
        os.makedirs(self.tokendir, exist_ok=True)
        with open(path, 'w') as fp:
            json.dump(token, fp, indent=4, sort_keys=True)

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

    def wait_authorization(self):
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

        self.save_token(self.token)
        self.get_email()

    def get(self, url, *, params=None):
        google = OAuth2Session(self.oauth_client, token=self.token,
            auto_refresh_url=self.token_url, auto_refresh_kwargs=self.extra,
            token_updater=self.save_token)
        r = google.get(url, params=params)
        r.raise_for_status()
        ret = r.json()
        return ret

    def post(self, url, *, data=None):
        if data is None:
            raise RuntimeError('post() data param must be set')
        google = OAuth2Session(self.oauth_client, token=self.token,
            auto_refresh_url=self.token_url, auto_refresh_kwargs=self.extra,
            token_updater=self.save_token)
        r = google.post(url, data=data)
        r.raise_for_status()
        ret = r.json()
        return ret
