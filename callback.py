from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse as parse
import sys
import asyncio
import os
import socket

import util

def makeAPIHandler(out, callback_url, credential):
    class APIHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                pp = parse.urlparse(self.path)
                query = parse.parse_qs(self.path)
                if pp.path == self.callback_url:
                    # debug
                    self.out.debug('callback from google')

                    if query.get('error') is not None:
                        self.out.message('oauth2 error, message={0}'.format(query.get('error')), True)
                        self.send_response(501)
                        self.send_header('content-type', 'text')
                        self.end_headers()
                        self.wfile.write('authorization failure. close this tab.\n\nphotod'.encode('utf-8'))
                    else:
                        if query.get('{}?state'.format(self.callback_url)) is not None and \
                                self.credential.authorization_state == query.get('{}?state'.format(self.callback_url))[0]:
                            self.credential.redirect_response = os.environ.get('BASE_URL') + self.path
                            self.send_response(200)
                            self.send_header('content-type', 'text')
                            self.end_headers()
                            self.wfile.write('authorized. close this tab.\n\nphotod'.encode('utf-8'))
                        else:
                            self.send_response(403)
                            self.send_header('content-type', 'text')
                            self.end_headers()
                            self.wfile.write('invalid state\n\nphotod'.encode('utf-8'))
                else:
                    self.send_response(404)
                    self.send_header('content-type', 'text')
                    self.end_headers()
                    self.wfile.write('not found\n\nphotod'.encode('utf-8'))
            except Exception as e:
                self.out.exception('error: APIHandler', e)

        def do_POST(self):
            self.send_response(501)
            self.send_header('content-type', 'text')
            self.end_headers()
            self.wfile.write('http 501\nphotod'.encode('utf-8'))
    ret = APIHandler
    ret.out = out
    ret.credential = credential
    ret.callback_url = callback_url
    return ret

class Callback():
    def __init__(self, loop, out, credential, callback_url):
        self.loop = loop
        self.out = out
        self.credential = credential
        self.callback_url = callback_url

    def run(self):
        try:
            asyncio.set_event_loop(self.loop)
            self.out.debug('launch callback service')
            self.out.info('callback service listen at {0}'.format(socket.gethostbyname_ex(socket.gethostname())))

            self.handler = makeAPIHandler(self.out, self.callback_url, self.credential)
            server = HTTPServer(('photod', 80), self.handler)
            server.serve_forever()
            self.out.error('callback server down!')
        except Exception as e:
            self.out.exception('error: callback.run()', e)
