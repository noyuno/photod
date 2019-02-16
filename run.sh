#!/bin/sh -e
mkdir -p ~/.aws
cat << EOF >~/.aws/credentials
[default]
aws_access_key_id = $AWS_ACCESS_KEY
aws_secret_access_key = $AWS_SECRET_KEY
EOF

cat << EOF >~/.aws/config
[default]
region=$AWS_REGION
EOF

python3 -u /opt/photod.py

