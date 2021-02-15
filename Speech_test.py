import logging
import os
import requests
import json
import sys
import time
import io
from flask import Flask, request, render_template, Response, url_for, jsonify
import urllib.parse

app = Flask(__name__)
port = os.getenv('PORT', '5030')

# Need these next two lines to eliminate the 'A secret key is required to use CSRF.' error
SECRET_KEY = os.urandom(32)
app.config['SECRET_KEY'] = SECRET_KEY

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

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
env_var = 'TTS_INSTANCE'
if env_var in os.environ:
    TTS_INSTANCE = os.environ[env_var]
else:
    raise Exception("Error no %s Defined!" % env_var)
env_var = 'STT_INSTANCE'
if env_var in os.environ:
    STT_INSTANCE = os.environ[env_var]
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
env_var = 'URL_ROOT'
if env_var in os.environ:
    url_root = os.environ[env_var]
else:
    url_root = ''
AUDIO_FORMAT = 'audio/mp3'

http_headers = {'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-Watson-Learning-Opt-Out': 'true',
                'X-Watson-Metadata': 'customer_id=Fred'}
stt_auth = ('apikey', STT_API_KEY),
tts_auth = ('apikey', TTS_API_KEY)


@app.before_request
def do_something_whenever_a_request_comes_in():
    logging.info('Environ:\t%s' % request.environ)
    logging.info('Path:\t%s' % request.path)
    logging.info('Full_path:\t%s' % request.full_path)
    logging.info('Script_root:\t%s' % request.script_root)
    logging.info('Url:\t%s' % request.url)
    logging.info('Base_url:\t%s' % request.base_url)
    logging.info('Url_root:\t%s' % request.url_root)
    logging.info('Scheme:\t%s' % request.scheme)


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
    logging.error('Error: %s' % str(e))
    return render_template('blank.html', message=str(e), title='Error!', url_root=url_root)


@app.route('/')
def welcomeToMyapp():
    return render_template('index.html', url_root=url_root)


@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('images/favicon-96x96.png')


@app.route('/build')
def build():
    return app.send_static_file('build.txt')


@app.route('/voices')
def voices():
    result = requests.get(TTS_API_URL + '/v1/voices', auth=tts_auth, headers=http_headers)
    if result.status_code == 200:
        voices = result.json()
        return jsonify(voices)
    else:
        raise Exception(result.content)

@app.route('/synthesize', methods=['GET', 'POST'])
def synthesize():
    result = requests.get(TTS_API_URL + '/v1/voices', auth=tts_auth, headers=http_headers)
    if result.status_code != 200:
        raise Exception('Error retrieving voices: %s - %s' % (result.status_code, result.content))
    content = result.json()
    voice_list = []
    for voice in content['voices']:
        voice_list.append({'name': voice['name'], 'description': voice['description']})

    return render_template('synthesize.html', url_root=url_root, voice_list=voice_list)


def synth():
    response = requests.get(TTS_API_URL + '/v1/synthesize', auth=tts_auth, params=payload)
    if response.status_code == 200:
        sound_data = response.content
        audio = AudioSegment.from_file(io.BytesIO(sound_data), format="mp3")


if __name__ == '__main__':
    logging.info('Starting %s....' % sys.argv[0])
    logging.info('Build: %s' % time.ctime(os.path.getmtime(sys.argv[0])))
    logging.info('Python: ' + sys.version)
    logging.info('Environment Variables:')

    app.run(host='0.0.0.0', port=int(port))

    payload = {'accept': AUDIO_FORMAT,
               'text': 'Hello world',
               'voice': 'en-GB_CharlotteV3Voice'
               }

    print('hi')
