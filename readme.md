# photod

A daemon that backup Google Photos albums to S3

## Backup

### Requirements

- [noyuno/discordbot](https://github.com/noyuno/discordbot)

### Settings

`docker-compose.yml` example:

~~~yaml
    photod:
        image: noyuno/photod:latest
        restart: always
        expose:
            - "80"
        #ports:
        #    - "8080:80"
        links:
            - discordbot
        environment:
            GOOGLE_OAUTH_CLIENT: ${GOOGLE_OAUTH_CLIENT}
            GOOGLE_OAUTH_SECRET: ${GOOGLE_OAUTH_SECRET}
            BASE_URL: "https://photos.${DOMAIN}"
            #BASE_URL: "http://localhost:8080"
            DISCORDBOT: "discordbot"
            AWS_ACCESS_KEY: ${AWS_ACCESS_KEY}
            AWS_SECRET_KEY: ${AWS_SECRET_KEY}
            S3_BUCKET: ${S3_BUCKET}
            S3_PREFIX: mirror/photod
            AWS_REGION: ${AWS_REGION}
        volumes:
            - ./data/photod:/data/photod/out
            - ./photod:/opt:ro
~~~


`docker-compose up -d photod`

## Download operation

~~~sh
docker run --rm -it -v $(pwd)/data:/data/photod/out -v $(pwd):/opt:ro \
    -e AWS_ACCESS_KEY=$AWS_ACCESS_KEY \
    -e AWS_SECRET_KEY=$AWS_SECRET_KEY \
    -e AWS_REGION=$AWS_REGION \
    -e S3_BUCKET=$S3_BUCKET \
    -e S3_PREFIX=$S3_PREFIX \
    -e EMAIL=$EMAIL \
    noyuno/photod /opt/download.sh
~~~

