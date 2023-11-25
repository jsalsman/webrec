# webrec
Record and Upload Audio with Stop on Silence

run: https://webrec.replit.app

dev: https://replit.com/@jsalsman/webrec

github: https://github.com/jsalsman/webrec

<img src="https://i.ibb.co/k69t7n5/Screenshot-20231124-005747.png" width=350 alt="screenshot"/>

Start at [templates/record.html](https://github.com/jsalsman/webrec/blob/main/templates/record.html)
for comments and code.

MIT license

# To do
- offer to reload on failed noise suppression toggle
- store audio in /static/
- limit uploads to 16000 * 2 * 60 + N bytes 
- reload after alert()
- unique filenames
- delete M oldest audio files after each upload
- disallow '..' etc. in downloads 
- Check back about errors (warnings?) from ort.js during vad.micVAD.new()
