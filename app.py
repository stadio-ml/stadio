from flask import Flask, send_file, session, jsonify, redirect, flash, url_for
from flask import render_template, request
from flask_cors import CORS
from werkzeug.utils import secure_filename
import random
import string
import os


UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'csv', 'txt'}



app = Flask(__name__, static_url_path="", static_folder="static")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = os.urandom(24)

CORS(app)

@app.route('/error', methods=["GET"])
def error():
    return "Error"

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return filename

@app.route('/evaluate', methods=["GET", "POST"])
def evaluate():
    print(session["submit_request_id"])
    print("data", request.data)
    print("args", request.args)
    print("form", request.form)

    if ("submit_request_id" not in session.keys()) or\
            (session["submit_request_id"] != request.form.get('submitRequestId', None)):
        return jsonify("error")

    if request.method == 'POST':
        print(request.files)
        # check if the post request has the file part
        if 'submittedSolutionFile' not in request.files:
            print('No file part')
            return redirect(request.url)
        file = request.files['submittedSolutionFile']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            print('No selected file')
            return redirect(request.url)
        if not allowed_file(file.filename):
            print('Unsupported file format.')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('uploaded_file',
                                    filename=filename))

    else:

        return redirect("/error")


@app.route('/submit', methods=["GET"])
def submit():
    submit_request_id = randomString(24)
    session["submit_request_id"] = submit_request_id
    return render_template("submit.html", submit_request_id=submit_request_id)









def randomString(stringLength=8):
    """Generate a random string of fixed length """
    letters= string.ascii_lowercase
    return ''.join(random.sample(letters, stringLength))


def check_file(filename):
    # check file size
    # check file schema
    # check file len
    return allowed_file(filename)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
