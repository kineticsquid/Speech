"""
https://cloud.ibm.com/docs/speech-to-text?topic=speech-to-text-websockets#websockets

Speech samples

https://raw.githubusercontent.com/Azure-Samples/cognitive-services-speech-sdk/f9807b1079f3a85f07cbb6d762c6b5449d536027/samples/cpp/windows/console/samples/whatstheweatherlike.wav
https://www.signalogic.com/index.pl?page=speech_codec_wav_samples
http://www.voiptroubleshooter.com/open_speech/american/OSR_us_000_0010_8k.wav - american
http://www.voiptroubleshooter.com/open_speech/american/OSR_us_000_0030_8k.wav - american
http://www.voiptroubleshooter.com/open_speech/british/OSR_uk_000_0020_8k.wav - british
http://www.voiptroubleshooter.com/open_speech/french/OSR_fr_000_0041_8k.wav - french

"""
import json
import requests
import websocket
import threading
from threading import Thread
import os
from base64 import b64encode
from ibm_watson import IAMTokenManager

env_var = 'STT_API_KEY'
if env_var in os.environ:
    STT_API_KEY = os.environ[env_var]
else:
    raise Exception("Error no %s Defined!" % env_var)
env_var = 'STT_API_URL'
if env_var in os.environ:
    STT_API_URL = os.environ[env_var]
else:
    raise Exception("Error no %s Defined!" % env_var)
env_var = 'STT_WS_URL'
if env_var in os.environ:
    STT_WS_URL = os.environ[env_var]
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

def get_audio_content():
    # f = open('static/audio/tts-lisa-intro.ogg', 'rb')
    # audio_content = f.read()
    # f.close()

    result = requests.get('https://raw.githubusercontent.com/Azure-Samples/cognitive-services-speech-sdk/f9807b1079f3a85f07cbb6d762c6b5449d536027/samples/cpp/windows/console/samples/whatstheweatherlike.wav')
    if result.status_code != 200:
        raise Exception('Error retrieving audo: %s' % result.status_code)

    return result.content

audio_content = get_audio_content()

iam_token_manager = IAMTokenManager(apikey=STT_API_KEY)
stt_access_token = iam_token_manager.get_token()
auth = b64encode(b"apikey:" + STT_API_KEY.encode('ascii')).decode("ascii")
headers = {'Authorization': 'Basic %s' % auth}

broadband_model = 'en-US_BroadbandModel'
telephony_model = 'en-US_Telephony'
narrowband_model = 'en-US_NarrowbandModel'
recognize_url = "%s/v1/recognize?access_token=%s&model=%s" % (STT_WS_URL, stt_access_token, telephony_model)
speech_url = 'https://www.signalogic.com/melp/EngSamples/Orig/male.wav'

output = []

def on_message(ws, message):
    print("### message ###")
    print(message)
    json_message = json.loads(message)
    results = json_message.get('audio_metrics', None)
    if results is not None:
        output.insert(0, json_message)
    results = json_message.get('results', None)
    if results is not None:
        output.append(json_message)
        result = results[0]
        final = result.get('final')
        if final:
            completed.set()

def on_error(ws, error):
    print("### error ###")
    print(error)

def on_close(ws):
    print("### closed ###")

def on_open(ws):
    print("### opened ###")
    msg = {"action": "start",
           "audio_metrics": True,
           "interim_results": True,
           "processing_metrics": True}
    ws.send(json.dumps(msg).encode('utf8'))
    started.set()

def ws_thread(ws):
    ws.run_forever()

started = threading.Event()
completed = threading.Event()
websocket.enableTrace(True)
ws = websocket.WebSocketApp(recognize_url, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close)
th = Thread(target=ws_thread, args=(ws,))
th.start()

started.wait(None)
ws.send(audio_content, opcode=websocket.ABNF.OPCODE_BINARY)
msg = {"action": "stop"}
ws.send(json.dumps(msg).encode('utf8'))

# Wait for 'final' to be set to true in results
completed.wait(None)
ws.close()

print('### output ###')
print(json.dumps(output, indent=4))
