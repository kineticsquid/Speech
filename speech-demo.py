
"""
https://cloud.ibm.com/docs/speech-to-text?topic=speech-to-text-websockets#websockets

Speech samples
https://upload.wikimedia.org/wikipedia/commons/d/d4/Samuel_George_Lewis.ogg
https://raw.githubusercontent.com/Azure-Samples/cognitive-services-speech-sdk/f9807b1079f3a85f07cbb6d762c6b5449d536027/samples/cpp/windows/console/samples/whatstheweatherlike.wav
https://www.signalogic.com/index.pl?page=speech_codec_wav_samples
http://www.voiptroubleshooter.com/open_speech/american/OSR_us_000_0010_8k.wav - american
http://www.voiptroubleshooter.com/open_speech/american/OSR_us_000_0030_8k.wav - american
http://www.voiptroubleshooter.com/open_speech/british/OSR_uk_000_0020_8k.wav - british
http://www.voiptroubleshooter.com/open_speech/french/OSR_fr_000_0041_8k.wav - french
"""
import os
import requests
import sys
from flask import Flask, request, render_template, jsonify, abort
import uuid
import json
from ibm_watson import IAMTokenManager
import threading
from threading import Thread
import websocket

app = Flask(__name__)

"""
For debugging
"""
def print_environment_variables():
    print('Environment Variables:')
    for key in os.environ.keys():
        print("\'%s\':\t\'%s\'" % (key, os.environ.get(key)))

# print_environment_variables()

# Audio formats supported by Speech to Text and Text to Speech
AUDIO_FORMATS = {
    'audio/basic',
    'audio/ogg',
    'audio/mp3',
    'audio/flac',
    'audio/mpeg',
    'audio/wav',
    'audio/webm'
}

app = Flask(__name__)
port = os.getenv('PORT', '5040')

# Need these next two lines to eliminate the 'A secret key is required to use CSRF.' error
SECRET_KEY = os.urandom(32)
app.config['SECRET_KEY'] = SECRET_KEY


env_var = 'TTS_API_URL'
if env_var in os.environ:
    TTS_API_URL = os.environ[env_var]
else:
    raise Exception("Error no %s Defined!" % env_var)
env_var = 'STT_API_URL'
if env_var in os.environ:
    STT_API_URL = os.environ[env_var]
else:
    raise Exception("Error no %s Defined!" % env_var)
env_var = 'TTS_API_KEY'
if env_var in os.environ:
    TTS_API_KEY = os.environ[env_var]
else:
    raise Exception("Error no %s Defined!" % env_var)
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
env_var = 'URL_ROOT'
if env_var in os.environ:
    url_root = os.environ[env_var]
else:
    url_root = ''
AUDIO_FORMAT = 'audio/ogg'

# Call to IAM to get an access token to use with STT websocket API.
http_headers = {'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-Watson-Learning-Opt-Out': 'true',
                'X-Watson-Metadata': 'customer_id=Fred'}
stt_auth = ('apikey', STT_API_KEY)
tts_auth = ('apikey', TTS_API_KEY)
iam_token_manager = IAMTokenManager(apikey=STT_API_KEY)
stt_access_token = iam_token_manager.get_token()

# Get the list of available TTS voices
result = requests.get(TTS_API_URL + '/v1/voices', auth=tts_auth, headers=http_headers)
if result.status_code != 200:
    raise Exception('Error retrieving voices: %s - %s' % (result.status_code, result.content))
content = result.json()
voice_list = []
for voice in content['voices']:
    voice_list.append({'name': voice['name'], 'description': voice['description']})

# Get the list of available STT language models
result = requests.get(STT_API_URL + '/v1/models', auth=stt_auth, headers=http_headers)
if result.status_code != 200:
    raise Exception('Error retrieving models: %s - %s' % (result.status_code, result.content))
content = result.json()
model_list = []
for model in content['models']:
    model_list.append({'name': model['name'], 'description': model['description']})


@app.before_request
def do_something_whenever_a_request_comes_in():
    r = request
    url = r.url
    method = r.method
    print('>>>> Call into Speech Test: %s ' % method, url)
    print('Environ:\t%s' % request.environ)
    print('Path:\t%s' % request.path)
    print('Full_path:\t%s' % request.full_path)
    print('Script_root:\t%s' % request.script_root)
    print('Url:\t%s' % request.url)
    print('Base_url:\t%s' % request.base_url)
    print('Url_root:\t%s' % request.url_root)
    print('Scheme:\t%s' % request.scheme)


@app.after_request
def apply_headers(response):
    # These are to fix low severity vulnerabilities identified by AppScan
    # in a dynamic scan. Also to prevent caching of content. Mostly to allow for rapid changing/debugging
    # of style sheets.
    response.headers['Content-Security-Policy'] = "object-src 'none'; script-src 'strict-dynamic'"
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response


@app.errorhandler(Exception)
def handle_bad_request(e):
    print('Error: %s' % str(e))
    return render_template('blank.html', message=str(e))


@app.route('/')
def welcomeToMyapp():
    return render_template('index.html')


@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('images/favicon-96x96.png')


@app.route('/voices')
def voices():
    result = requests.get(TTS_API_URL + '/v1/voices', auth=tts_auth, headers=http_headers)
    if result.status_code == 200:
        voices = result.json()
        return jsonify(voices)
    else:
        raise Exception(result.content)

@app.route('/tts', methods=['GET', 'POST'])
def tts():

    return render_template('tts.html',
                           voice_list=voice_list,
                           voice="Lisa: American English female voice. Dnn technology.",
                           audio_format_list=AUDIO_FORMATS,
                           audio_file="static/audio/tts-lisa-intro.ogg",
                           audio_format="audio/ogg")

@app.route('/synthesize', methods=['GET', 'POST'])
def synthesize():
    form = request.form
    text = form['text_to_synthsize']
    voice = form['voice']
    audio_format = form['audio_format']

    headers = {"Content-Type": "application/json", "accept": audio_format}
    parameters = {'voice': voice}
    payload = {"text": text}

    response = requests.post(TTS_API_URL + '/v1/synthesize',
                            auth=tts_auth,
                            headers=headers,
                            params=parameters,
                            data=json.dumps(payload))
    if response.status_code == 200:
        sound_data = response.content
        index = audio_format.find('/')
        file_type = audio_format[index+1:len(audio_format)]
        audio_filename = "static/audio/%s.%s" % (str(uuid.uuid1()), file_type)
        f = open(audio_filename, 'wb')
        f.write(sound_data)
        f.close()
        print('returning audio from %s' % audio_filename)
        return render_template('tts.html',
                               voice_list=voice_list,
                               voice=voice,
                               audio_format_list=AUDIO_FORMATS,
                               audio_file=audio_filename,
                               audio_format=audio_format)
    else:
        message = "Error synthesizing \'%s\' with voice \'%s\'.\n<br>%s - %s" % (text,
                                                                                 voice,
                                                                                 response.status_code,
                                                                                 response.content)
        return render_template('blank.html',
                               message=message)

@app.route('/play', defaults={'file_path': ''})
@app.route('/play/<path:file_path>')
def play(file_path):
    BASE_DIR = './static/audio'
    abs_path = os.path.join(BASE_DIR, file_path)
    if not os.path.exists(abs_path):
        return abort(404)

    if os.path.isfile(abs_path):
        return render_template('play.html',
                               audio_file=abs_path)
    else:
        files = os.listdir(abs_path)
        return render_template('list_files.html', files=files)

@app.route('/models')
def models():
    result = requests.get(STT_API_URL + '/v1/models', auth=stt_auth, headers=http_headers)
    if result.status_code == 200:
        models = result.json()
        return jsonify(models)
    else:
        raise Exception(result.content)

@app.route('/stt', methods=['GET', 'POST'])
def stt():
    m = model_list
    return render_template('stt.html',
                           model_list=model_list,
                           audio_file="static/audio/stt-kate-intro.ogg",
                           audio_format="audio/ogg")

@app.route('/transcribe', methods=['GET', 'POST'])
def transcribe():
    form = request.form
    audio_url = form['url_to_transcribe']
    model = form['model']
    audio_metrics = form.get('audio_metrics', None)
    if audio_metrics is None:
        audio_metrics = False
    else:
        audio_metrics = True
    processing_metrics = form.get('processing_metrics', None)
    if processing_metrics is None:
        processing_metrics = False
    else:
        processing_metrics = True
    interim_results = form.get('interim_results', None)
    if interim_results is None:
        interim_results = False
    else:
        interim_results = True

    # Added this User-Agent header to eliminate 406 error
    result = requests.get(audio_url, headers={"User-Agent": "XY"})
    if result.status_code != 200:
        raise Exception('Error %s retrieving audio file \'%s\'.' % (result.status_code, audio_url))
    audio_content = result.content
    recognize_url = "%s/v1/recognize?access_token=%s&model=%s" % (STT_WS_URL, stt_access_token, model)

    # output and final_text are arrays used to get results back from the websocket callback routines below.
    output = []
    final_text = []
    # started is set once the websocket interface is open and stt indicates that it is listening
    started = threading.Event()
    # completed is set once we see final=true in the transcription results
    completed = threading.Event()

    # on_message, on_open, on_close, on_error are for handling callbacks from websocket
    def on_message(ws, message):
        # this does the heavy lifting to process the transcription results. It looks for a 'final' flag
        # in the transcription results and when found signals the completed event.
        print("### message ###")
        print(message)
        json_message = json.loads(message)
        # check first to see if STT flagged an error, which comes back in the message payload. if so, set the
        # completed event to stop processing
        error = json_message.get('error', None)
        if error is not None:
            output.append(json_message)
            completed.set()
        # Look for audio metrics and if found, add to output
        results = json_message.get('audio_metrics', None)
        if results is not None:
            output.insert(0, json_message)
        results = json_message.get('results', None)
        # Look for transcription results and process
        if results is not None:
            output.append(json_message)
            result = results[0]
            final = result.get('final')
            if final:
                # If final is set we know we have the final transcription results, so record this
                alternatives = result.get('alternatives')
                if alternatives is not None and len(alternatives) > 0:
                    final_text.append(alternatives[0]['transcript'])
                completed.set()

    def on_error(ws, error):
        print("### error ###")
        print(error)

    def on_close(ws):
        print("### closed ###")

    def on_open(ws):
        print("### opened ###")
        msg = {"action": "start",
               "audio_metrics": audio_metrics,
               "interim_results": interim_results,
               "processing_metrics": processing_metrics}
        ws.send(json.dumps(msg).encode('utf8'))
        started.set()

    def ws_thread(ws):
        ws.run_forever()

    # open the websocket and start a thread for processing
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp(recognize_url, on_open=on_open, on_message=on_message, on_error=on_error,
                                on_close=on_close)
    th = Thread(target=ws_thread, args=(ws,))
    th.start()

    # wait for the started event to indicate that STT is listening
    started.wait(None)
    ws.send(audio_content, opcode=websocket.ABNF.OPCODE_BINARY)
    msg = {"action": "stop"}
    ws.send(json.dumps(msg).encode('utf8'))

    # Wait for the completed event, which is set once we see the final transcription results.
    completed.wait(None)
    ws.close()
    if len(final_text) > 0:
        text = final_text[0]
    else:
        text = ''
    return render_template('stt.html',
                           final_text=text,
                           output=json.dumps(output, indent=4),
                           model_list=model_list,
                           audio_file=audio_url,
                           audio_title="%s - %s" % (model, audio_url))

@app.route('/build', methods=['GET', 'POST'])
def build():
    try:
        build_file = open('static/build.txt')
        build_stamp = build_file.readlines()[0]
        build_file.close()
    except FileNotFoundError:
        from datetime import date
        build_stamp = generate_build_stamp()
    results = 'Running %s %s.\nBuild %s.\nPython %s.' % (sys.argv[0], app.name, build_stamp, sys.version)
    return results

def generate_build_stamp():
    from datetime import date
    return 'Development build - %s' % date.today().strftime("%m/%d/%y")

print('Starting %s %s' % (sys.argv[0], app.name))
print('Python: ' + sys.version)
try:
    build_file = open('static/build.txt')
    build_stamp = build_file.readlines()[0]
    build_file.close()
except FileNotFoundError:
    from datetime import date
    build_stamp = generate_build_stamp()
print('Running build: %s' % build_stamp)

print('Environment Variables:')
environment_vars = dict(os.environ)
for key in environment_vars.keys():
    print('%s: %s\n' % (key, environment_vars[key]))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

