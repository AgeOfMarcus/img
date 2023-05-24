from dotenv import load_dotenv
load_dotenv()

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

from flask import Flask, send_file, redirect as _redirect, request, render_template, jsonify
from flask_cors import CORS
from magic import Magic
import os, uuid, base64, json, io, lzma

from resize import smaller_than

creds = credentials.Certificate(json.loads(base64.b64decode(os.getenv("CREDS")).decode()))
firebase_admin.initialize_app(creds)
db = firestore.client().collection('images')
lnks = firestore.client().collection('links')
URL = 'https://i.marcusj.tech'

app = Flask(__name__)
CORS(app)
magic = Magic(mime=True)

def decompress(raw):
    try:
        return lzma.decompress(raw)
    except lzma.LZMAError:
        return raw

def check_image(im):
    optimal = smaller_than(im, 1048487)
    file = io.BytesIO()
    im.save(file, quality=optimal, format='PNG')
    return file.getvalue()

def redirect(route):
    return _redirect(f'https://{request.host}{route}')

@app.route('/')
def app_index():
    return render_template('index.html')

@app.route('/assets/<fn>')
def app_asset(fn):
    if fn in os.listdir('assets'):
        return send_file('assets/' + fn)
    return 'eat shit'

@app.route('/api/docs')
def app_api_docs():
    return render_template('docs.html')

@app.route('/upload', methods=['POST'])
def app_upload():
    image = request.files.get('image')
    if image:
        data = image.read()
        mimetype = magic.from_buffer(data)
        if not mimetype.startswith('image'):
            return 'error: file is not a valid image', 422
        raw = mimetype.encode() + b':::' + lzma.compress(data)
        enc = base64.b64encode(raw).decode()
        uid = str(uuid.uuid4()).replace('-','')
        doc = db.document(uid)
        doc.set({'image': enc})
        return redirect(f'/view/{uid}')
    return 'error: no image', 400

@app.route('/api/upload', methods=['POST'])
def app_api_upload():
    image = request.files.get('image')
    if image:
        data = image.read()
        mimetype = magic.from_buffer(data)
        if not mimetype.startswith('image'):
            return 'error: file is not a valid image', 422
        raw = mimetype.encode() + b':::' + lzma.compress(data)
        enc = base64.b64encode(raw).decode()
        uid = str(uuid.uuid4()).replace('-','')
        doc = db.document(uid)
        doc.set({'image': enc})
        return jsonify({'url': f'{URL}/image/{uid}'})
    return 'error: no image', 400

@app.route('/view/<uid>')
def app_view(uid):
    return render_template('view.html', uuid=uid)

@app.route('/image/<uid>')
@app.route('/image/<uid>/.png')
@app.route('/image/<uid>.png')
@app.route('/image/<uid>/<fn>.png')
def app_image(uid, fn=None):
    data = db.document(uid).get().get('image')
    if data:
        mime, img = base64.b64decode(data).split(b':::')
        return send_file(
            io.BytesIO(decompress(img)),
            mimetype=mime.decode(),
            as_attachment=False,
        )
    return 'error: image not found', 404

@app.route('/shorten/<uid>')
def app_shorten(uid):
    nuid = str(uuid.uuid4()).replace('-','')
    if db.document(uid).get().exists:
        chrs = 1
        while lnks.document(nuid[:chrs]).get().exists:
            chrs += 1
            if chrs >= len(nuid):
                nuid += str(uuid.uuid4()).replace('-','')
        shrt = nuid[:chrs]
        lnks.document(shrt).set({'uuid': uid})
        return redirect(f'/i/{shrt}')
    return 'error: no image with that uuid exists', 404

@app.route('/i/<shrt>')
@app.route('/i/<shrt>/.png')
@app.route('/i/<shrt>.png')
@app.route('/i/<shrt>/<fn>.png')
def app_view_shrt(shrt, fn=None):
    uid = lnks.document(shrt).get().get('uuid')
    if uid:
        data = db.document(uid).get().get('image')
        mime, img = base64.b64decode(data).split(b':::')
        return send_file(
            io.BytesIO(decompress(img)),
            mimetype=mime.decode(),
            as_attachment=False,
        )
    return 'error: image not found', 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)