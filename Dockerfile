from python:3-alpine

run apk update && \
    pip install schedule requests requests_oauthlib
cmd python3 -u /opt/photod.py

