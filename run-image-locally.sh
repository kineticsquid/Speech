#!/bin/bash

export DATE=`date '+%F_%H:%M:%S'`

# Now run locally. Use "rm" to remove the container once it finishes
docker run --rm -p 5005:5005 \
  --env DATE=$DATE \
  --env STT_API_KEY=${STT_API_KEY} \
  --env TTS_API_KEY=${TTS_API_KEY} \
  --env STT_API_URL=${STT_API_URL} \
  --env TTS_API_URL=${TTS_API_URL} \
  --env STT_WS_URL=${STT_WS_URL} \
  --env STT_HOST=${STT_HOST} \
  --env STT_PORT=${STT_PORT} \
  --env PORT=${PORT} \
  kineticsquid/speech-demo:latest



