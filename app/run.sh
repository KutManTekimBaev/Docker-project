#!/bin/bash
NETWORK=appnet
DB_CONTAINER=db
CACHE_CONTAINER=cache
WEB_CONTAINER=web

if docker network inspect $NETWORK >/dev/null 2>&1; then
 echo "Network $NETWORK alredy exist"
else
 echo "Creating network $NETWORK..."
docker network create appnet
fi

if docker volume inspect appvol >/dev/null 2>&1; then
    echo "Volume appvol already exists"
else
    echo "Creating volume appvol..."
    docker volume create appvol
fi

start_container() {
CONTAINER_NAME=$1
RUN_COMMAND=$2

if [ "$(docker ps -q -f name=^/${CONTAINER_NAME}$)" ]; then
echo "Container $CONTAINER_NAME already running"

elif [ "$(docker ps -aq -f name=^/${CONTAINER_NAME}$)" ]; then
echo "Starting existing container $CONTAINER_NAME..."
docker start $CONTAINER_NAME

else
echo "Creating container $CONTAINER_NAME..."
eval "$RUN_COMMAND"
fi
}
start_container "$DB_CONTAINER" "docker run -d --name db --network appnet --env-file db.env -v appvol:/var/lib/postgresql/data postgres:15"
start_container "$CACHE_CONTAINER" "docker run -d --name cache --network appnet redis"
start_container "$WEB_CONTAINER" "docker run -d --name web --network appnet --env-file web.env -p 8080:8080 myapp:v1"
