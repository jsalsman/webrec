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
from flask_socketio import SocketIO
import sox                     # needs command line sox and the pysox package
from datetime import datetime  # for audio file timestamps
import os                      # to delete old audio files
from time import time          # to keep files less than 10 minutes old

from sys import stderr  # best for Replit; you may want to import logging
log = lambda message: stderr.write(message + '\n')  # ...and connect this

app = Flask(__name__)
socketio = SocketIO(app)

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
    wav_filename = f"audio-{timestamp}.wav"

    audio_file.save('static/' + raw_filename)

    # Convert format, trim silence
    tfm = sox.Transformer()
    tfm.set_input_format(file_type='raw', rate=16000, bits=16, 
               channels=1, encoding='signed-integer')

    tfm.silence(min_silence_duration=0.25,  # remove lengthy silence 
      buffer_around_silence=True)  # replace removals with 1/4 second
    # https://pysox.readthedocs.io/en/latest/api.html#sox.transform.Transformer.silence
         
    tfm.build('static/' + raw_filename, 'static/' + wav_filename)
    duration = sox.file_info.duration('static/' + wav_filename)

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
    
    log(f'Built {wav_filename} ({duration:.1f} seconds.) ' +
        f'All audio using {audio_space:.2f} MB.')
  
    return redirect(f'/playback/{wav_filename}')

  return "No audio file", 400

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
  
app.run(host='0.0.0.0', port=81)
# TODO: production WSGI server
# see https://replit.com/talk/learn/How-to-set-up-production-environment-for-your-Flask-project-on-Replit/139169
