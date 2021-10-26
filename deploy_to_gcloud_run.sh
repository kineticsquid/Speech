#!/bin/bash

echo 'Be sure to "gcloud auth login" first'

export DATE=`date '+%F_%H:%M:%S'`

# Run this to create or re-deploy the function
gcloud run deploy speech-demo --allow-unauthenticated --project cloud-run-stuff --region us-central1 \
  --source ./ --set-env-vars=DATE=$DATE \
  --set-env-vars STT_API_KEY=${STT_API_KEY} \
  --set-env-vars TTS_API_KEY=${TTS_API_KEY} \
  --set-env-vars STT_API_URL=${STT_API_URL} \
  --set-env-vars TTS_API_URL=${TTS_API_URL} \
  --set-env-vars STT_WS_URL=${STT_WS_URL} \
  --set-env-vars STT_HOST=${STT_HOST} \
  --set-env-vars STT_PORT=${STT_PORT}