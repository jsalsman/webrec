from flask import (Flask, request, render_template, url_for, 
                   redirect, send_from_directory)
import sox
from time import time

app = Flask(__name__)

@app.route('/')  # redirect from / to /record
def index():
    return redirect ('/record')

@app.route('/record')  # show recording UI
def record():
    return render_template('record.html')

@app.route('/upload-audio', methods=['POST'])  # accept file from recorder
def upload_audio():
    if 'audio' in request.files:
        audio_file = request.files['audio']
        audio_path = "./uploaded_audio.wav"
        audio_file.save(audio_path)

        # Trim silence #and normalize levels
        tfm = sox.Transformer()
        tfm.silence()
        #tfm.compand()
        #tfm.norm()
        trimmed_audio_path = "./audio.wav"
        tfm.build(audio_path, trimmed_audio_path)

        return redirect(url_for('playback', audio_path=trimmed_audio_path))
    return "No audio file", 400

@app.route('/get-audio/<filename>')  # download the trimmed audio
def get_audio(filename):
    return send_from_directory('.', 'audio.wav')  # was filename, less secure

@app.route('/playback')  # provide an autoplay audio player with controls
def playback():
    audio_path = request.args.get('audio_path')
    current_time = time()  # for bypassing browser cache
    return render_template('playback.html', audio_path=audio_path,
                           time=current_time)

@app.route('/static/<path:path>')  # serve javascript and favicon files
def send_js(path):
    return send_from_directory('static', path)

app.run(host='0.0.0.0', port=81)
