# photod

A daemon that backup Google Photos albums to S3

## Backup

### Requirements

- [noyuno/discordbot](https://github.com/noyuno/discordbot)
- HTTPS proxy server (such as [noyuno/k2: my server (Kagoya Version 2 server)](https://github.com/noyuno/k2))
- Google Photos Library API, People API
- S3

### Settings

`docker-compose.yml` example:

~~~yaml
    nginx:
        image: steveltn/https-portal:1
        ports:
            - 80:80
            - 443:443
        restart: always
        environment:
            STAGE: production
            DOMAINS: |
                photos.${DOMAIN} -> http://photod:80

    photod:
        image: noyuno/photod:latest
        restart: always
        expose:
            - "80"
        links:
            - discordbot
            - nginx
        environment:
            GOOGLE_OAUTH_CLIENT: ${GOOGLE_OAUTH_CLIENT}
            GOOGLE_OAUTH_SECRET: ${GOOGLE_OAUTH_SECRET}
            BASE_URL: "https://photos.${DOMAIN}"
            DISCORDBOT: "discordbot"
            AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
            AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
            S3_BUCKET: ${S3_BUCKET}
            S3_PREFIX: mirror/photod
            AWS_REGION: ${AWS_REGION}
            SCHEDULE_TIME: "17:51" # requires zero fill 02:51
            SCHEDULE_WEEKDAY: "0,1,2,3,4,5,6"
            #ONESHOT: 1
        volumes:
            - ./data/photod:/data/photod
            - ./logs/photod:/logs/photod
            - ./photod:/opt/photod:ro
~~~


`docker-compose up -d photod`

## Download operation

~~~sh
docker run --rm -it \
    -v $(pwd)/out:/data/photod \
    -v $(pwd):/opt/photod:ro \
    -v $(pwd)/logs:/logs/photod \
    -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
    -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
    -e AWS_REGION=$AWS_REGION \
    -e S3_BUCKET=$S3_BUCKET \
    -e S3_PREFIX=mirror/photod \
    -e EMAIL=$EMAIL noyuno/photod /opt/photod/download.sh
~~~
