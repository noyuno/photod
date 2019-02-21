from python:3-alpine

run apk update && \
    pip install schedule requests requests_oauthlib boto3
cmd /opt/photod/run.sh

