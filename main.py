from flask import Flask, request, render_template,  redirect, send_from_directory
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
    audio_file = request.files.get('audio')
    if audio_file:
        audio_file.save("audio.raw")

        # Convert format, trim silence #and normalize levels
        tfm = sox.Transformer()
        tfm.set_input_format(file_type='raw', rate=16000, bits=16, 
                             channels=1, encoding='signed-integer')
        tfm.silence()
        #tfm.compand()
        #tfm.norm()
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
