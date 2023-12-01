# webrec: Record and Upload Audio with Stop on Silence
#
# See templates/record.html for primary comments and main javascript code.
#
# This application is released under the MIT License, November 24, 2023.
#
# run: https://webrec.replit.app
# dev: https://replit.com/@jsalsman/webrec
# github: https://github.com/jsalsman/webrec

from flask import (Flask, request, render_template,  redirect,
                   send_from_directory)
from flask_socketio import SocketIO  # Fails over to POST submissions
import sox                     # needs command line sox and the pysox package
import lameenc                 # to produce .mp3 files for playback
from datetime import datetime  # for audio file timestamps
import os                      # to delete old audio files
from time import time          # to keep files less than 10 minutes old

from sys import stderr
def log(message):  # best for Replit; you probably want to 'import logging'
  stderr.write(message + '\n')  # ...and connect this body of log(m) instead

app = Flask(__name__)
socketio = SocketIO(app)  # Socket.IO server

@app.route('/')  # redirect from / to /record
def index():
  return redirect ('/record')

@app.route('/record')  # show recording UI
def record():
  return render_template('record.html', 
                         force_click='forceClick' in request.args)

@app.route('/upload-audio', methods=['POST'])
def upload_audio():
  audio_file = request.files.get('audio')
  if audio_file:
    if len(audio_file.read()) > 16000 * 2 * 61:  # over 1m01s
      return 'File too big', 400
    audio_file.seek(0)

    timestamp = datetime.now().strftime("%M%S%f")[:8]  # MMSSssss
    raw_filename = f"audio-{timestamp}.raw"

    audio_file.save('static/' + raw_filename)

    return redirect('/playback/' +  # return new url to play
                    process_file(raw_filename))  # see below

  return "No audio file", 400

def process_file(raw_filename):
  # Convert format, trim silence
  tfm = sox.Transformer()
  tfm.set_input_format(file_type='raw', rate=16000, bits=16, 
             channels=1, encoding='signed-integer')

  tfm.silence(min_silence_duration=0.25,  # remove lengthy silence 
    buffer_around_silence=True)  # replace removals with 1/4 second
  # https://pysox.readthedocs.io/en/latest/api.html#sox.transform.Transformer.silence

  #pcm = tfm.build_array('static/' + raw_filename)  # FAILS
  # https://github.com/rabitt/pysox/issues/154

  tfm.build('static/' + raw_filename, 'static/tmp-' + raw_filename)

  # Set up the MP3 encoder
  encoder = lameenc.Encoder()
  encoder.set_in_sample_rate(16000)
  encoder.set_channels(1)
  encoder.set_bit_rate(64)  # https://github.com/chrisstaite/lameenc/blob/main/lameenc.c
  encoder.set_quality(2)  # https://github.com/gypified/libmp3lame/blob/master/include/lame.h

  # Encode the PCM data to MP3
  with open('static/tmp-' + raw_filename, 'rb') as f:
    mp3_data = encoder.encode(f.read())
  mp3_data += encoder.flush()
  os.remove('static/tmp-' + raw_filename)
  
  mp3_fn = raw_filename.replace('.raw', '.mp3')

  with open('static/' + mp3_fn, 'wb') as f:
    f.write(mp3_data)
  
  duration = sox.file_info.duration('static/' + mp3_fn)
  
  # Clean up older files; maximum 40 MB will remain
  files = [os.path.join('static', f) for f in
     os.listdir('static') if f.startswith('audio-')]
  # Sort files by last modified time, oldest first
  files.sort(key=lambda x: os.path.getmtime(x))
  current_time = time()
  # Remove all but the 10 most recent audio files
  for file in files[:-10]:
    # Get the modification time of the file
    mod_time = os.path.getmtime(file)
    # Calculate the age of the file in seconds
    file_age = current_time - mod_time
    # Check if the file is older than 10 minutes
    if file_age > 600:
      os.remove(file)
  audio_space = sum([os.path.getsize('static/' + f) 
                     for f in os.listdir('static')
                     if f.startswith('audio-')]) / (1024 ** 2)

  log(f'Built {mp3_fn} ({duration:.1f} seconds.) ' +
      f'All audio using {audio_space:.2f} MB.')
  return mp3_fn

@app.route('/playback/<fn>')
def playback(fn):
    size = os.path.getsize('static/' + fn) / 1024  # Size in KB
    duration = sox.file_info.duration('static/' + fn)  # Duration in seconds
    full_url = request.url_root + 'get_audio/' + fn
    clean_url = full_url.replace('http://', '').replace('https://', '')
    return render_template('playback.html', audio=fn, url=clean_url,
                           size=f'{size:.1f}', duration=f'{duration:.1f}')

@app.route('/get-audio/<filename>')  # download the trimmed audio
def get_audio(filename):
  return send_from_directory('static', filename)  # safe against ../...

@app.route('/static/<path:path>')  # javascript, audio, and favicon files
def send_js(path):
  return send_from_directory('static', path) # safe against ../...

# Clean up all the audio files when script starts, to avoid dev confusion
for file in [os.path.join('static', f) for f in os.listdir('static') 
             if f.startswith('audio-')]:
  os.remove(file)

# Socket.IO implementation
active_streams = {}   # Only using atomic dict operations
sid_to_filename = {}  # ...in ways that are thread safe.

@socketio.on('connect')
def websocket_connect():
  timestamp = datetime.now().strftime("%H%M%S%f")[:8]
  sid_to_filename[request.sid] = f"audio-{timestamp}.raw"

@socketio.on('audio_chunk')
def websocket_chunk(data):
  if request.sid not in active_streams:
    active_streams[request.sid] = open('static/' + 
       sid_to_filename[request.sid], 'wb')
  active_streams[request.sid].write(data)

@socketio.on('end_recording')
def socket_end():
  try:
    active_streams[request.sid].close()
    del active_streams[request.sid]
    mp3_fn = process_file(sid_to_filename[request.sid])  # See above
    del sid_to_filename[request.sid]
    return '/playback/' + mp3_fn
  except Exception as e:
    log(f"Error ending recording: {e}")
    active_streams.pop(request.sid, None)   # del dict entries
    sid_to_filename.pop(request.sid, None)  # even if already del'd
    return 'fail', str(e)

@socketio.on('start_over')
def start_over():
  if request.sid in active_streams:
    log('**STARTING OVER***')
    active_streams[request.sid].seek(0)     # start again at the beginning
    active_streams[request.sid].truncate()  # clear existing data to overwrite

#app.run(host='0.0.0.0', port=81)  # using Sockets.IO
socketio.run(app, host='0.0.0.0', port=81, 
             allow_unsafe_werkzeug=True)  # deployment error workaround

# TODO? production WSGI server
# see https://replit.com/talk/learn/How-to-set-up-production-environment-for-your-Flask-project-on-Replit/139169
