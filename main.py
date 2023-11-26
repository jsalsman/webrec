# webrec: Record and Upload Audio with Stop on Silence
#
# See templates/record.html for primary comments and main javascript code.
#
# This application is released under the MIT License, November 24, 2023.
#
# run: https://webrec.replit.app
# dev: https://replit.com/@jsalsman/webrec
# github: https://github.com/jsalsman/webrec

from flask import Flask, request, render_template,  redirect, send_from_directory
from flask_socketio import SocketIO, emit  # Fails over to POST submissions
import sox                     # needs command line sox and the pysox package
import lameenc                 # to produce .mp3 files for playback
from datetime import datetime  # for audio file timestamps
import os                      # to delete old audio files
from time import time          # to keep files less than 10 minutes old

from sys import stderr  # best for Replit; you may want to 'import logging'
log = lambda message: stderr.write(message + '\n')  # ...and connect this

app = Flask(__name__)
socketio = SocketIO(app)  # Websocket

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

    return redirect(f'/playback/' + process_file(raw_filename))

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
  # sox/transform.py", line 793, in build_array
  #    encoding_out = [
  # IndexError: list index out of range

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

@app.route('/playback/<filename>')
def playback(filename):
  return render_template('playback.html', audio=filename)

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

# WebSocket implementation
active_streams = {}
sid_to_filename = {}

@socketio.on('connect')
def websocket_connect():
  timestamp = datetime.now().strftime("%H%M%S%f")[:8]
  sid_to_filename[request.sid] = f"audio-{timestamp}.raw"

@socketio.on('audio_chunk')
def websocket_chunk(data):
  try:
    if request.sid not in active_streams:
      filename = sid_to_filename[request.sid]
      active_streams[request.sid] = open(f'static/{filename}', 'wb')
    active_streams[request.sid].write(data)
  except Exception as e:
    log(f"Error writing audio data: {e}")
    return 'fail', repr(e)

@socketio.on('end_recording')
def websocket_end():
  try:
    if request.sid in active_streams:
      active_streams[request.sid].close()
      filename = sid_to_filename[request.sid]
      mp3_fn = process_file(filename)  # See above
      del active_streams[request.sid]
      del sid_to_filename[request.sid]
      return '/playback/' + mp3_fn
  except Exception as e:
    log(f"Error ending websocket: {e}")
    return 'fail', repr(e)

#app.run(host='0.0.0.0', port=81)
socketio.run(app, host='0.0.0.0', port=81)

# TODO? production WSGI server
# see https://replit.com/talk/learn/How-to-set-up-production-environment-for-your-Flask-project-on-Replit/139169
