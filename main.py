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
import sox  # needs command line sox and the pysox package
from time import time

app = Flask(__name__)

@app.route('/')  # redirect from / to /record
def index():
    return redirect ('/record')

@app.route('/record')  # show recording UI
def record():
    return render_template('record.html')  # see for more detailed comments

@app.route('/upload-audio', methods=['POST'])  # accept file from recorder
def upload_audio():
    audio_file = request.files.get('audio')
    if audio_file:
        audio_file.save("audio.raw")

        # Convert format, trim silence
        tfm = sox.Transformer()
        tfm.set_input_format(file_type='raw', rate=16000, bits=16, 
                             channels=1, encoding='signed-integer')

        tfm.silence(min_silence_duration=0.25,  # remove lengthy silence 
            buffer_around_silence=True)  # replace removals with 1/4 second
        # https://pysox.readthedocs.io/en/latest/api.html#sox.transform.Transformer.silence
        # TODO: probably need silence_threshold > 0.1 default?

        #tfm.vad(location=1, normalize=False)   # voice activity detection
        #tfm.vad(location=-1, normalize=False)  # ...and from end  
        # https://pysox.readthedocs.io/en/latest/api.html#sox.transform.Transformer.vad
               
        tfm.build("audio.raw", "audio.wav")

        return redirect('/playback/audio.wav')
    return "No audio file", 400

@app.route('/playback/<filename>')  # autoplay audio player
def playback(filename):
    current_time = time()  # for bypassing browser cache
    return render_template('playback.html', audio=filename,
                           time=current_time)

@app.route('/get-audio/<filename>')  # download the trimmed audio
def get_audio(filename):
    return send_from_directory('.', filename)  # TODO: make safer

@app.route('/static/<path:path>')  # javascript and favicon files
def send_js(path):
    return send_from_directory('static', path)

app.run(host='0.0.0.0', port=81)
