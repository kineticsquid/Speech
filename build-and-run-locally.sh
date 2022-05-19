#!/bin/bash
echo "Tagging and pushing docker image. Be sure to start docker.app first"
echo "To examine contents: 'docker run -it sudoku-main sh'"
echo "Need to be logged on first with 'bx login --sso'. "

docker rmi kineticsquid/speech-demo:latest
docker build --rm --no-cache --pull -t kineticsquid/speech-demo:latest -f Dockerfile .
docker push kineticsquid/speech-demo:latest

# list the current images
echo "Docker Images..."
docker images

echo "Now running..."
./.vscode/run-image-locally.sh
