"""
https://cloud.ibm.com/docs/speech-to-text?topic=speech-to-text-websockets#websockets
"""
import asyncio
import requests
import json
import ssl
import os
from base64 import b64encode
from ibm_watson import IAMTokenManager
from autobahn.asyncio.websocket import WebSocketClientProtocol, WebSocketClientFactory

env_var = 'STT_API_KEY'
if env_var in os.environ:
    STT_API_KEY = os.environ[env_var]
else:
    raise Exception("Error no %s Defined!" % env_var)
env_var = 'STT_WS_URL'
if env_var in os.environ:
    STT_WS_URL = os.environ[env_var]
else:
    raise Exception("Error no %s Defined!" % env_var)
env_var = 'STT_API_URL'
if env_var in os.environ:
    STT_API_URL = os.environ[env_var]
else:
    raise Exception("Error no %s Defined!" % env_var)
env_var = 'STT_HOST'
if env_var in os.environ:
    STT_HOST = os.environ[env_var]
else:
    raise Exception("Error no %s Defined!" % env_var)
env_var = 'STT_PORT'
if env_var in os.environ:
    STT_PORT = os.environ[env_var]
else:
    raise Exception("Error no %s Defined!" % env_var)


def get_STT_models():
    stt_auth = ('apikey', STT_API_KEY)
    models_url = "%s/v1/models" % STT_API_URL
    http_headers = {'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-Watson-Learning-Opt-Out': 'true'}
    result = requests.get(models_url, auth=stt_auth, headers=http_headers)
    if result.status_code != 200:
        raise Exception('Error retrieving models: %s - %s' % (result.status_code, result.content))
    content = result.json()
    models = content['models']
    return models

class MyClientProtocol(WebSocketClientProtocol):

    def onConnect(self, response):
        print('OnConnect:')
        print(json.dumps(response.headers, indent=4))
    def onConnecting(self, transport_details):
        print('OnConnecting:')
        print('Transport_details: %s' % transport_details.peer)

    def onOpen(self):
        print('OnOpen:')
        print('Sending start')
        start_msg = {"action": "start",
                     "audio_metrics": True,
                     "interim_results": True,
                     "processing_metrics": True}
        self.sendMessage(json.dumps(start_msg).encode('utf8'))
        print('Sending audio')
        self.sendMessage(audio_content, isBinary=True)
        print('Sending stop')
        self.sendMessage(json.dumps({"action": "stop"}).encode('utf8'))

    def onClose(self, wasClean, code, reason):
        print('OnClose:')
        print('wasClean: %s. code: %s. reason: %s', (wasClean, code, reason))

    def onMessage(self, payload, isBinary):
        print('OnMessage:')
        if isBinary:
            print("Binary message received: {0} bytes".format(len(payload)))
        else:
            print("Text message received: {0}".format(payload.decode('utf8')))

    def hw(self, msg):
        print("hw:")
        print(msg)

f = open('static/audio/lisa-intro.ogg', 'rb')
audio_content = f.read()
f.close()

# models = get_STT_models()
# print(json.dumps(models, indent=4))

iam_token_manager = IAMTokenManager(apikey=STT_API_KEY)
access_token = iam_token_manager.get_token()
language_model = 'en-US_BroadbandModel'
recognize_url = "%s/v1/recognize?x-watson-learning-opt-out=true" % STT_WS_URL
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

factory = WebSocketClientFactory(url=recognize_url)
factory.protocol = MyClientProtocol
auth = b64encode(b"apikey:" + STT_API_KEY.encode('ascii')).decode("ascii")
headers = {'Authorization': 'Basic %s' % auth}
factory.headers = headers

event_loop = asyncio.get_event_loop()
coroutine = event_loop.create_connection(factory, host=STT_HOST, port=STT_PORT, ssl=context)
event_loop.run_until_complete(coroutine)
event_loop.run_forever()
# event_loop.close()