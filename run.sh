#!/bin/sh -e
mkdir -p ~/.aws

if [ ! "$AWS_ACCESS_KEY_ID" -o ! "$AWS_SECRET_ACCESS_KEY" -o ! "$AWS_REGION" ]; then
    echo "Required environment variable not set. It requires AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION" >&2
    exit 1
fi

cat << EOF >~/.aws/credentials
[default]
aws_access_key_id = $AWS_ACCESS_KEY_ID
aws_secret_access_key = $AWS_SECRET_ACCESS_KEY
EOF

cat << EOF >~/.aws/config
[default]
region=$AWS_REGION
EOF

python3 -u /opt/photod/main.py

