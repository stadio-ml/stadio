import traceback

from flask import Flask, send_file, session, jsonify, redirect, flash, url_for, request
from flask import render_template, request
from flask_cors import CORS
from werkzeug.utils import secure_filename
import competition_tools
import os
import secrets
from api_utils import ApiAuth
from models import db, Submission, Evaluation
from competition_tools import eval_public_private
from sqlalchemy import func
from datetime import datetime

#TODO Load configuration from config.yaml
UPLOAD_FOLDER = './uploads'
TEST_FILE_PATH = './static/test_solution/test_solution.csv'
MAX_FILE_SIZE = 32 * 1024 * 1024  # limit upload file size to 32MB
API_FILE = 'mappings.dummy.json'
DB_FILE = 'sqlite:///test.db'
TIME_BETWEEN_SUBMISSIONS = 5 * 60 # 5 minutes between submissions

# function that maps db-stored score to printable value
# TODO: move somewhere appropriate
score_mapper = lambda score: f"{score*100:.2f}"


app = Flask(__name__, static_url_path="", static_folder="static")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
app.secret_key = os.urandom(24)

CORS(app)

api_auth = ApiAuth(API_FILE)
app.config["SQLALCHEMY_DATABASE_URI"] = DB_FILE
db.init_app(app)
db.app = app
db.create_all()

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

@app.route('/', methods=["GET"])
def leaderboard():
    # TODO: here, we assume that a higher score is preferable.
    # it might not always be like this (e.g. MSE)
    # For those cases, func.min should be used: make this parameter
    # configurable from config file
    participants = db.session \
        .query(Submission.user_id, func.max(Evaluation.evaluation_public)) \
        .join(Submission) \
        .group_by(Submission.user_id) \
        .order_by(Evaluation.evaluation_public.desc()) \
        .all()
    score = request.args.get("score")
    highlight_user_id = request.args.get("highlight")
    participants = [ (user_id, score_mapper(score)) for user_id, score in participants ]
    if score:
        try:
            score = score_mapper(float(score))
        except: # Just in case someone passes something nasty for `score`
            score = None
    return render_template("leaderboard.html", score=score, highlight_user_id=highlight_user_id, participants=participants)

################
# Evaluate
################
@app.route('/evaluate', methods=["GET"])
def evaluate():
    try:
        api_key = request.args.get("api_key")
        submission_id = request.args.get("submission_id")
        if not api_auth.is_valid(api_key):
            # TODO build dictionary of possible errors & avoid hardcoding strings
            raise Exception("Invalid API key!")

        user_id = api_auth.get_user(api_key)
        submission = Submission.query.filter_by(id=submission_id, user_id=user_id).first()
        public_score, private_score = eval_public_private(submission.filename, TEST_FILE_PATH)
        if not submission:
            # not found!
            raise Exception("Submission not found!")

    except Exception as ex:
        traceback.print_stack()
        traceback.print_exc()
        return redirect(url_for('error', error_message=ex))

    evaluation = Evaluation(submission=submission, evaluation_public=public_score, evaluation_private=private_score)
    db.session.add(evaluation)
    db.session.commit()
    return redirect(url_for('leaderboard', score=public_score, highlight=user_id))


################
# Upload
################
@app.route('/upload', methods=["POST"])
def upload():
    error_message = ""
    # Check submit request id

    try:
        if ("submit_request_id" not in session.keys()) or \
                (session["submit_request_id"] != request.form.get('submitRequestId', None)):
            error_message = "Wrong request. Use the form web page to upload a solution or try to reload the page!"
            raise Exception(error_message)

        #TODO check API_KEY from request.form.get("APIKey", None)
        api_key = request.form.get("APIKey", None)
        if not api_auth.is_valid(api_key):
            raise Exception("Invalid API key!")
        user_id = api_auth.get_user(api_key) # This will be stored in the Submissions table

        # Save submitted solution
        if request.method == 'POST':
            latest_submission = db.session.query(func.max(Submission.timestamp)).filter(Submission.user_id == user_id).first()[0]
            now = datetime.utcnow()
            if latest_submission and (now - latest_submission).total_seconds() < TIME_BETWEEN_SUBMISSIONS:
                delta = max(5, int(TIME_BETWEEN_SUBMISSIONS - (now - latest_submission).total_seconds())) # avoid messages such as "try again in 0/1/2 seconds" (TODO remove magic number 5)
                raise Exception(f"You are exceeding the {TIME_BETWEEN_SUBMISSIONS} seconds limit between submissions. Please try again in {delta} seconds")
            
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
                new_file_name = f"{timestamp}_{user_id}.csv"
                output_file = os.path.join(app.config['UPLOAD_FOLDER'], new_file_name)
                # we are reading the stream when checking the file, so we need to go back to the start
                file.stream.seek(0)
                file.save(output_file)
                submission = Submission(user_id=user_id, filename=output_file)
                db.session.add(submission)
                db.session.commit()
                # By passing api_key, we can later check that the user calling /evaluate
                # is the same that has made the submission
                return redirect(url_for('evaluate', submission_id=submission.id, api_key=api_key))
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
