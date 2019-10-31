import traceback

from flask import Flask, send_file, session, jsonify, redirect, flash, url_for
from flask import render_template, request
from flask_cors import CORS
from werkzeug.utils import secure_filename
import competition_tools
import os
import secrets
from api_utils import ApiAuth

#TODO Load configuration from config.yaml
UPLOAD_FOLDER = './uploads'
TEST_FILE_PATH = './static/test_solution/test_solution.csv'
MAX_FILE_SIZE = 32 * 1024 * 1024  # limit upload file size to 32MB
API_FILE = 'mappings.dummy.json'


app = Flask(__name__, static_url_path="", static_folder="static")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
app.secret_key = os.urandom(24)

CORS(app)

api_auth = ApiAuth(API_FILE)

################
# Error Handling
################
@app.errorhandler(413)
def request_entity_too_large(error):
    return render_template('error.html', error_message = str(error)), 413

@app.errorhandler(404)
def request_entity_too_large(error):
    return render_template('error.html', error_message = str(error)), 404

@app.route('/error', methods=["GET"])
def error():
    error_message = request.args["error_message"]
    return render_template('error.html', error_message = str(error_message))


################
# Evaluate
################
@app.route('/evaluate', methods=["GET"])
def evaluate():
    try:
        if ("submit_request_id" not in session.keys()) or \
                (session["submit_request_id"] != request.args.get('submitRequestId', None)):
            error_message = "Wrong request. Use the form web page to upload a solution or try to reload the page!"
            raise Exception(error_message)

        submitted_to_evaluate = request.args["submitted_to_evaluate"]

        # TODO run evaluation here

    except Exception as ex:
        traceback.print_stack()
        traceback.print_exc()
        return redirect(url_for('error', error_message=ex))

    return jsonify(submitted_to_evaluate)


################
# Upload
################
@app.route('/upload', methods=["POST"])
def upload():
    error_message = ""
    # Check submit request id
    print(request.files)

    try:
        if ("submit_request_id" not in session.keys()) or \
                (session["submit_request_id"] != request.form.get('submitRequestId', None)):
            error_message = "Wrong request. Use the form web page to upload a solution or try to reload the page!"
            raise Exception(error_message)

        #TODO check API_KEY from request.form.get("APIKey", None)
        api_key = request.form.get("APIKey", None)
        if not api_auth.is_valid(api_key):
            raise Exception("Invalid API key!")

        # Save submitted solution
        if request.method == 'POST':
            # check if the post request has the file part
            if 'submittedSolutionFile' not in request.files:
                error_message ='No file part'
                raise Exception(error_message)

            file = request.files['submittedSolutionFile']

            # if user does not select file, browser also
            # submit an empty part without filename
            if file.filename == '':
                error_message ='No selected file'
                raise Exception(error_message)
            elif competition_tools.check_file(file, TEST_FILE_PATH) == False:
                error_message = 'Wrong file schema.'
                raise Exception(error_message)
            elif competition_tools.allowed_file(file.filename) == False:
                error_message ='Unsupported file format.'
                raise Exception(error_message)

            elif file:
                timestamp = competition_tools.get_timestamp()
                new_file_name = f"{timestamp}_{api_key}.csv"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_file_name))
                return redirect(url_for('evaluate',
                                        submitted_to_evaluate=new_file_name,
                                        submitRequestId=session["submit_request_id"]))
            else:
                raise Exception("You should not be here!")
    except Exception as ex:
        traceback.print_stack()
        traceback.print_exc()
        return redirect(url_for('error', error_message=ex))

################
# Submit
################
@app.route('/submit', methods=["GET"])
def submit():
    submit_request_id = secrets.token_hex()
    session["submit_request_id"] = submit_request_id
    return render_template("submit.html", submit_request_id=submit_request_id)



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
