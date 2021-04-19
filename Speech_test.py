import os
import requests
import json
import sys
import time
import io
from flask import Flask, request, render_template, Response, url_for, jsonify, send_from_directory, abort
import urllib.parse
import uuid

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
port = os.getenv('PORT', '5030')

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
AUDIO_FORMAT = 'audio/ogg'

http_headers = {'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-Watson-Learning-Opt-Out': 'true',
                'X-Watson-Metadata': 'customer_id=Fred'}
stt_auth = ('apikey', STT_API_KEY),
tts_auth = ('apikey', TTS_API_KEY)

result = requests.get(TTS_API_URL + '/v1/voices', auth=tts_auth, headers=http_headers)
if result.status_code != 200:
    raise Exception('Error retrieving voices: %s - %s' % (result.status_code, result.content))
content = result.json()
voice_list = []
for voice in content['voices']:
    voice_list.append({'name': voice['name'], 'description': voice['description']})


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

@app.route('/input', methods=['GET', 'POST'])
def input():

    return render_template('input.html',
                           url_root=url_root,
                           voice_list=voice_list,
                           voice="Lisa: American English female voice. Dnn technology.",
                           audio_format_list=AUDIO_FORMATS,
                           audio_file="static/audio/lisa-intro.ogg",
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
        return render_template('input.html',
                               url_root=url_root,
                               voice_list=voice_list,
                               voice=voice,
                               audio_format_list=AUDIO_FORMATS,
                               audio_file=audio_filename,
                               audio_format=audio_format)
        # return render_template('play.html',
        #                        audio_file=audio_filename,
        #                        audio_format=audio_format,
        #                        url_root=url_root)
    else:
        message = "Error synthesizing \'%s\' with voice \'%s\'.\n<br>%s - %s" % (text,
                                                                                 voice,
                                                                                 response.status_code,
                                                                                 response.content)
        return render_template('blank.html',
                               url_root=url_root,
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
                           audio_file=abs_path,
                           # audio_format="audio/mp3",
                           url_root=url_root)
    else:
        files = os.listdir(abs_path)
        return render_template('list_files.html', files=files, url_root=url_root)

@app.route('/speak', methods=['GET', 'POST'])
def speak():
    return render_template('speak.html',
                           url_root=url_root)

if __name__ == '__main__':
    print('Starting %s....' % sys.argv[0])
    print('Python: ' + sys.version)
    print("url_root: %s" % url_root)
    print('Environment Variables:')
    for key in os.environ.keys():
        print('%s:\t%s' % (key, os.environ.get(key)))

    app.run(host='0.0.0.0', port=int(port))

