import traceback
from flask import Flask, session, redirect, url_for
from flask import render_template, request
from flask_cors import CORS
import competition_tools
import os
import secrets
from api_utils import ApiAuth
from models import db, Submission, Evaluation
from competition_tools import (
    eval_public_private,
    StageHandler,
    get_private_leaderboard,
    get_public_leaderboard,
    score_mapper,
)
from evaluation_functions import evaluator_name, to_maximize
from sqlalchemy import func
from datetime import datetime
import pandas as pd
import numpy as np
from scipy.stats import trim_mean


app = Flask(__name__, static_url_path="", static_folder="static")
app.config.from_object("config.CompetitionConfig")
app.secret_key = os.urandom(24)

CORS(app)

stage_handler = StageHandler(
    app.config["OPEN_TIME"], app.config["CLOSE_TIME"], app.config["TERMINATE_TIME"]
)
api_auth = ApiAuth(app.config["API_FILE"])
app.config["SQLALCHEMY_DATABASE_URI"] = app.config["DB_FILE"]
db.init_app(app)
db.app = app
db.create_all()

# Sanity checks
competition_tools.check_solution_file(app.config["TEST_FILE_PATH"])

# Scheduling database dumps
competition_tools.schedule_db_dump(
    app.config["CLOSE_TIME"],
    db,
    stage_name="CLOSE",
    dump_out=app.config["DUMP_FOLDER"],
)
competition_tools.schedule_db_dump(
    app.config["TERMINATE_TIME"],
    db,
    stage_name="TERMINATE",
    dump_out=app.config["DUMP_FOLDER"],
)


def get_user_id(api_key):
    if not api_auth.is_valid_key(api_key):
        # TODO build dictionary of possible errors & avoid hardcoding strings
        raise Exception("Invalid API key!")
    user_id = api_auth.get_user(api_key)
    return user_id


@app.route("/dashboard_login", methods=["GET"])
def dashboard_login():
    api_key = request.args.get("api_key")
    try:
        request_user_id = get_user_id(api_key)
        # print(request_user_id)
        if request_user_id not in [app.config["ADMIN_USER_ID"]]:
            return redirect(url_for("leaderboard"))
    except Exception as ex:
        traceback.print_stack()
        traceback.print_exc()
        return redirect(url_for("error", error_message=ex))

    session["dashboard_login"] = True

    return redirect(url_for("general_dashboard"))


@app.route("/dashboard_logout", methods=["GET"])
def dashboard_logout():
    session.pop("dashboard_login", None)
    return redirect(url_for("leaderboard"))


###################
# Student_dashboard
###################
@app.route("/student_dashboard", methods=["GET"])
@app.route("/student_dashboard/<string:user_id>", methods=["GET"])
def student_dashboard(user_id=None):
    try:
        if ("dashboard_login" not in session.keys()) or (
            session["dashboard_login"] is False
        ):
            error_message = "Login to access the dashboard!"
            raise Exception(error_message)
    except Exception as ex:
        traceback.print_stack()
        traceback.print_exc()
        return redirect(url_for("error", error_message=ex))

    pub_leader = competition_tools.get_public_leaderboard(db)
    priv_leader = competition_tools.get_private_leaderboard(db, stage_handler)

    pub_leader_df = pd.DataFrame(pub_leader, columns=["user_id", "public"])
    priv_leader_df = pd.DataFrame(priv_leader, columns=["user_id", "private"])

    # TODO manage empty leaderboard
    pub_priv_leader_df = pd.merge(
        pub_leader_df, priv_leader_df, on="user_id", validate="one_to_one"
    )

    if user_id is None:
        return render_template(
            "student_dashboard.html",
            user_id=user_id,
            leaderboard=pub_priv_leader_df.to_dict(orient="index"),
            selected_user_id=user_id,
        )

    else:
        try:
            if user_id not in pub_priv_leader_df["user_id"].values:
                raise Exception(f"User {user_id} not found.")

            pub_position = (
                np.where(
                    pub_priv_leader_df.sort_values(["public"], ascending=False)[
                        "user_id"
                    ].values
                    == user_id
                )[0][0]
                + 1
            )
            priv_position = (
                np.where(
                    pub_priv_leader_df.sort_values(["private"], ascending=False)[
                        "user_id"
                    ].values
                    == user_id
                )[0][0]
                + 1
            )

            priv_score_on_leaderboard = pub_priv_leader_df.loc[
                pub_position - 1, "private"
            ]

            user_scores = competition_tools.get_user_scores(
                db, user_id, sort_descending=to_maximize
            )

            user_scores = pd.DataFrame(user_scores).rename(
                {0: "user_id", 1: "timestamp", 2: "public", 3: "private"}, axis=1
            )
            user_scores["public"] = user_scores["public"].astype(float)
            user_scores["private"] = user_scores["private"].astype(float)

            user_scores = user_scores.replace([np.inf, -np.inf], np.nan)

            n_submissions = len(user_scores)

            max_public = competition_tools.score_mapper(user_scores["public"].max())
            avg_public = competition_tools.score_mapper(
                trim_mean(user_scores["public"], 0.1)
            )
            std_public = competition_tools.score_mapper(user_scores["public"].std())

            max_private = competition_tools.score_mapper(user_scores["private"].max())
            avg_private = competition_tools.score_mapper(
                trim_mean(user_scores["private"], 0.1)
            )
            std_private = competition_tools.score_mapper(user_scores["private"].std())

            user_scores_sub_freq = user_scores.copy()
            # user_scores_sub_freq["timestamp"] = pd.to_datetime(user_scores["timestamp"])

            user_scores_sub_freq = (
                user_scores_sub_freq.groupby(pd.Grouper(key="timestamp", freq="1D"))
                .size()
                .to_frame()
                .rename({0: "count"}, axis=1)
                .reset_index()
            )

            # compute KPI
            return render_template(
                "student_dashboard.html",
                user_id=user_id,
                leaderboard=pub_priv_leader_df.to_dict(orient="index"),
                selected_user_id=user_id,
                pub_position=pub_position,
                priv_position=priv_position,
                priv_score_on_leaderboard=priv_score_on_leaderboard,
                n_submissions=n_submissions,
                max_public=max_public,
                avg_public=avg_public,
                std_public=std_public,
                max_private=max_private,
                avg_private=avg_private,
                std_private=std_private,
                user_scores=user_scores.to_json(orient="index"),
                user_scores_sub_freq=user_scores_sub_freq.to_json(orient="index"),
            )
        except Exception as ex:
            traceback.print_stack()
            traceback.print_exc()
            return redirect(url_for("error", error_message=ex))

            # return render_template("student_dashboard.html", leaderboard=pub_priv_leader_df.to_dict(orient="index"),
            #                        error=str(ex))


@app.route("/general_dashboard", methods=["GET"])
def general_dashboard():
    try:
        if ("dashboard_login" not in session.keys()) or (
            session["dashboard_login"] is False
        ):
            error_message = "Login to access the dashboard!"
            raise Exception(error_message)
    except Exception as ex:
        traceback.print_stack()
        traceback.print_exc()
        return redirect(url_for("error", error_message=ex))

    try:
        pub_leader = competition_tools.get_public_leaderboard(db)
        priv_leader = competition_tools.get_private_leaderboard(db, stage_handler)
        pub_leader_df = pd.DataFrame(pub_leader, columns=["user_id", "public"])
        priv_leader_df = pd.DataFrame(priv_leader, columns=["user_id", "private"])
        pub_priv_leader_df = pd.merge(
            pub_leader_df, priv_leader_df, on="user_id", validate="one_to_one"
        )

        pub_priv_leader_df.private = pub_priv_leader_df.private.astype(float)
        pub_priv_leader_df.public = pub_priv_leader_df.public.astype(float)

        # Here eventual -Inf values in the dataframe are omitted from statistics.
        # TODO consider trimmed mean?
        submission_info = dict(
            last_update=datetime.now(),
            count=competition_tools.get_submissions_number(db),
            public_mean=score_mapper(pub_priv_leader_df.public.mean()),
            public_std=score_mapper(pub_priv_leader_df.public.std()),
            private_mean=score_mapper(pub_priv_leader_df.private.mean()),
            private_std=score_mapper(pub_priv_leader_df.private.std()),
        )

        competition_info = dict(
            name=app.config["NAME"],
            open_time=app.config["OPEN_TIME"],
            close_time=app.config["CLOSE_TIME"],
            evaluator_name=evaluator_name,
        )

        peruser_submission_number = pd.DataFrame(
            competition_tools.get_peruser_submissions_number(db),
            columns=["user_id", "submission_count"],
        )
        peruser_info = pd.merge(
            peruser_submission_number,
            pub_priv_leader_df,
            on="user_id",
            validate="one_to_one",
        ).set_index("user_id")

        # ??get and filter baseline score to provide it separately
        try:
            baseline_info = peruser_info.loc[app.config["BASELINE_USER_ID"]]
        except Exception as ex:
            traceback.print_stack()
            traceback.print_exc()
            baseline_info = None

        try:
            peruser_info = peruser_info.loc[
                peruser_info.index != app.config["BASELINE_USER_ID"]
            ]
        except Exception as ex:
            traceback.print_stack()
            traceback.print_exc()
            peruser_info = None

        return render_template(
            "general_dashboard.html",
            competition_info=competition_info,
            submission_info=submission_info,
            peruser_info=peruser_info.to_json(orient="index")
            if peruser_info is not None
            else None,
            baseline_info=baseline_info.to_json(orient="index")
            if baseline_info is not None
            else None,
        )

    except Exception as ex:
        traceback.print_stack()
        traceback.print_exc()
        return redirect(url_for("error", error_message=ex))


################
# Error Handling
################
@app.errorhandler(413)
def error_handler_413(error):
    return render_template("error.html", error_message=str(error)), 413


@app.errorhandler(404)
def error_handler_404(error):
    return render_template("error.html", error_message=str(error)), 404


@app.route("/error", methods=["GET"])
def error():
    error_message = request.args["error_message"]
    return render_template("error.html", error_message=str(error_message))


####################
# update submissions
####################
@app.route("/update_submissions", methods=["POST"])
def update_submissions():
    if not api_auth.is_valid_key(session["api_key"]):
        raise Exception("Invalid API key!")

    user_id = api_auth.get_user(session["api_key"])
    checked_submission_ids = [int(checked_s_id) for checked_s_id in request.form]
    # print("checked_submission_ids:", checked_submission_ids)

    try:
        with_success = True
        user_evals = (
            db.session.query(Evaluation)
            .join(Submission)
            .filter_by(user_id=user_id)
            .all()
        )

        if len(checked_submission_ids) > 2:
            raise Exception(
                f"Only two submissions can be selected for the final evaluation. You selected {len(user_evals)}."
            )

        # print("user_evals:", user_evals)

        for e in user_evals:
            e.private_check = False
            if e.submission_id in checked_submission_ids:
                e.private_check = True

        db.session.commit()
        return render_template("update_submissions.html", with_success=with_success)

    except Exception as ex:
        with_success = False
        db.session.rollback()
        traceback.print_stack()
        traceback.print_exc()
        return render_template(
            "update_submissions.html", with_success=with_success, ex=str(ex)
        )


################
# submissions
################
@app.route("/submissions", methods=["GET", "POST"])
def submissions():
    # TODO allow to admins the access
    if stage_handler.is_ready():
        return render_template(
            "ready.html",
            name=app.config["NAME"],
            open_time=stage_handler.open_time,
            close_time=stage_handler.close_time,
        )

    if stage_handler.is_terminated():
        return render_template("over.html", name=app.config["NAME"])

    # Get API key from submissions form and show submissions
    api_key = request.form.get("APIKey", None)

    if api_key is None:
        submissions_request_id = secrets.token_hex()
        session["submissions_request_id"] = submissions_request_id
        return render_template(
            "submissions.html",
            submissions_request_id=submissions_request_id,
            is_closed=stage_handler.is_closed(),
        )
    else:
        try:
            if ("submissions_request_id" not in session.keys()) or (
                session["submissions_request_id"]
                != request.form.get("submissionsRequestId", None)
            ):
                error_message = "Wrong request. Use the form web page to upload a solution or try to reload the page!"
                raise Exception(error_message)
            if not api_auth.is_valid_key(api_key):
                raise Exception("Invalid API key!")

            session["api_key"] = api_key
            user_id = api_auth.get_user(api_key)

            app.logger.info(
                f"Received request to check submissions page by user_id '{user_id}'."
            )

            Submission.query.filter_by(user_id=user_id).all()

            user_submissions = (
                db.session.query(
                    Submission.id,
                    Submission.user_id,
                    Submission.timestamp,
                    Evaluation.evaluation_public,
                    Evaluation.private_check,
                )
                .join(Submission)
                .filter_by(user_id=user_id)
                .all()
            )
            # print(user_submissions)
            user_submissions = [
                (s_id, timestamp, user_id, competition_tools.score_mapper(score), check)
                for s_id, timestamp, user_id, score, check in user_submissions
            ]

            submissions_left = int(
                app.config["MAX_NUMBER_SUBMISSIONS"]
                - competition_tools.get_user_submissions_number(user_id=user_id, db=db)
            )

            return render_template(
                "submissions.html",
                submissions_request_id=session["submissions_request_id"],
                user_id=user_id,
                user_submissions=user_submissions,
                is_closed=stage_handler.is_closed(),
                left=submissions_left,
            )

        except Exception as ex:
            traceback.print_stack()
            traceback.print_exc()
            return redirect(url_for("error", error_message=ex))


################
# leaderboard
################


@app.route("/", methods=["GET"])
def leaderboard():
    try:
        # To allow access to admins even is competition is ready or over
        user_id = None
        api_key = request.args.get("api_key", None)
        if api_key is not None:
            user_id = get_user_id(api_key)
            app.logger.info(
                f"Received request to leaderboard page by user_id '{user_id}'."
            )

        if (
            (user_id is None) or (user_id not in [app.config["ADMIN_USER_ID"]])
        ) and stage_handler.is_ready():
            return render_template(
                "ready.html",
                name=app.config["NAME"],
                open_time=stage_handler.open_time,
                close_time=stage_handler.close_time,
            )
        elif (
            (user_id is None) or (user_id not in [app.config["ADMIN_USER_ID"]])
        ) and stage_handler.is_terminated():
            return render_template("over.html", name=app.config["NAME"])
        else:
            participants = get_public_leaderboard(db, maximized_score=to_maximize)
            score = request.args.get("score")
            highlight_user_id = request.args.get("highlight")

            if score:
                try:
                    score = competition_tools.score_mapper(float(score))
                except:  # Just in case someone passes something nasty for `score`
                    score = None

            left = request.args.get("left", None)
            return render_template(
                "leaderboard.html",
                name=app.config["NAME"],
                score=score,
                highlight_user_id=highlight_user_id,
                participants=participants,
                can_submit=True,
                close_time=stage_handler.close_time,
                is_closed=stage_handler.is_closed(),
                left=left,
                evaluator_name=evaluator_name,
            )

    except Exception as ex:
        traceback.print_stack()
        traceback.print_exc()
        return redirect(url_for("error", error_message=ex))


###################
# final leaderboard
###################


@app.route("/fleaderboard", methods=["GET"])
def fleaderboard():

    try:
        user_id = None
        api_key = request.args.get("api_key", None)
        if api_key is not None:
            user_id = get_user_id(api_key)
            app.logger.info(
                f"Received request to final leaderboard page by user_id '{user_id}'."
            )

    except Exception as ex:
        traceback.print_stack()
        traceback.print_exc()
        return redirect(url_for("error", error_message=ex))

    if (user_id is None) or (user_id not in [app.config["ADMIN_USER_ID"]]):
        return redirect(url_for("leaderboard"))

    participants = get_private_leaderboard(
        db, stage_handler, maximized_score=to_maximize
    )

    return render_template(
        "leaderboard.html", participants=participants, can_submit=False
    )


################
# Show evaluate score
################
@app.route("/show_evaluate_score", methods=["GET"])
def show_evaluate_score():
    return render_template(
        "evaluation_score.html",
        pub_score=request.args.get("pub_score"),
        priv_score=request.args.get("priv_score"),
        baseline=int(request.args.get("baseline")),
    )


################
# Evaluate
################
@app.route("/evaluate", methods=["GET"])
def evaluate():
    try:
        api_key = request.args.get("api_key")
        user_id = get_user_id(api_key)

        if (
            user_id not in [app.config["ADMIN_USER_ID"], app.config["BASELINE_USER_ID"]]
        ) and (not stage_handler.can_submit()):
            return redirect(url_for("leaderboard"))
        else:

            submission_id = request.args.get("submission_id")
            submission = Submission.query.filter_by(
                id=submission_id, user_id=user_id
            ).first()
            public_score, private_score = eval_public_private(
                submission.filename, app.config["TEST_FILE_PATH"]
            )
            if not submission:
                # not found!
                raise Exception("Submission not found!")

            if user_id == app.config["ADMIN_USER_ID"]:
                return redirect(
                    url_for(
                        "show_evaluate_score",
                        pub_score=public_score,
                        priv_score=private_score,
                        baseline=0,
                    )
                )
            else:
                evaluation = Evaluation(
                    submission=submission,
                    evaluation_public=public_score,
                    evaluation_private=private_score,
                )
                db.session.add(evaluation)
                db.session.commit()

                if user_id == app.config["BASELINE_USER_ID"]:
                    return redirect(
                        url_for(
                            "show_evaluate_score",
                            pub_score=public_score,
                            priv_score=private_score,
                            baseline=1,
                        )
                    )
                else:
                    submissions_left = int(
                        app.config["MAX_NUMBER_SUBMISSIONS"]
                        - competition_tools.get_user_submissions_number(
                            user_id=user_id, db=db
                        )
                    )

                    return redirect(
                        url_for(
                            "leaderboard",
                            score=public_score,
                            highlight=user_id,
                            left=submissions_left,
                        )
                    )

    except Exception as ex:
        traceback.print_stack()
        traceback.print_exc()
        return redirect(url_for("error", error_message=ex))


################
# Upload
################
@app.route("/upload", methods=["POST"])
def upload():
    try:
        api_key = request.form.get("api_key", None)
        user_id = get_user_id(api_key)  # This will be stored in the Submissions table

        # TODO Handle this. Doing so, a student who loaded the page before the deadline can still perform the submission
        if (
            user_id not in [app.config["ADMIN_USER_ID"], app.config["BASELINE_USER_ID"]]
        ) and (not stage_handler.can_submit()):
            return redirect(url_for("leaderboard"))
        else:
            error_message = ""
            # Check submit request id

            if ("submit_request_id" not in session.keys()) or (
                session["submit_request_id"]
                != request.form.get("submitRequestId", None)
            ):
                error_message = "Wrong request. Use the form web page to upload a solution or try to reload the page!"
                raise Exception(error_message)

            # Save submitted solution
            if request.method == "POST":

                latest_submission = (
                    db.session.query(func.max(Submission.timestamp))
                    .filter(Submission.user_id == user_id)
                    .first()[0]
                )
                now = datetime.utcnow()

                if user_id not in [
                    app.config["ADMIN_USER_ID"],
                    app.config["BASELINE_USER_ID"],
                ]:

                    if (
                        latest_submission
                        and (now - latest_submission).total_seconds()
                        < app.config["TIME_BETWEEN_SUBMISSIONS"]
                    ):
                        delta = max(
                            5,
                            int(
                                app.config["TIME_BETWEEN_SUBMISSIONS"]
                                - (now - latest_submission).total_seconds()
                            ),
                        )  # avoid messages such as "try again in 0/1/2 seconds" (TODO remove magic number 5)
                        raise Exception(
                            f"You are exceeding the {app.config['TIME_BETWEEN_SUBMISSIONS']} seconds limit between submissions. Please try again in {delta} seconds"
                        )

                    n_submissions = competition_tools.get_user_submissions_number(
                        user_id=user_id, db=db
                    )
                    if n_submissions >= app.config["MAX_NUMBER_SUBMISSIONS"]:
                        raise Exception(
                            f"You are exceeding the max submissions limit of {app.config['MAX_NUMBER_SUBMISSIONS']}. "
                            f"You are no more allowed to submit any solution."
                        )

                # check if the post request has the file part
                if "submittedSolutionFile" not in request.files:
                    error_message = "No file part"
                    raise Exception(error_message)

                file = request.files["submittedSolutionFile"]
                if not file:
                    error_message = "Error uploading solution file."
                    raise Exception(error_message)

                # if user does not select file, browser also
                # submit an empty part without filename
                if file.filename == "":
                    error_message = "No selected file"
                    raise Exception(error_message)

                if competition_tools.allowed_file(
                    file.filename
                ) and competition_tools.check_file(file, app.config["TEST_FILE_PATH"]):

                    timestamp = competition_tools.get_timestamp()
                    new_file_name = f"{timestamp}_{user_id}.csv"
                    output_file = os.path.join(
                        app.config["UPLOAD_FOLDER"], new_file_name
                    )
                    # we are reading the stream when checking the file, so we need to go back to the start
                    file.stream.seek(0)
                    file.save(output_file)
                    submission = Submission(user_id=user_id, filename=output_file)
                    db.session.add(submission)
                    db.session.commit()
                    # By passing api_key, we can later check that the user calling /evaluate
                    # is the same that has made the submission
                    return redirect(
                        url_for(
                            "evaluate", submission_id=submission.id, api_key=api_key
                        )
                    )
                else:
                    raise Exception("You should not be here!")

    except Exception as ex:
        traceback.print_stack()
        traceback.print_exc()
        return redirect(url_for("error", error_message=ex))


################
# Submit
################
@app.route("/submit", methods=["GET"])
def submit():
    try:
        user_id = None
        api_key = request.args.get("api_key", None)
        if api_key is not None:
            user_id = get_user_id(api_key)
            app.logger.info(
                f"Received request to submission page by user_id '{user_id}'."
            )

        if ((user_id is None) or (user_id not in [app.config["ADMIN_USER_ID"]])) and (
            not stage_handler.can_submit()
        ):
            return redirect(url_for("leaderboard"))
        else:
            submit_request_id = secrets.token_hex()
            session["submit_request_id"] = submit_request_id
            return render_template(
                "submit.html",
                submit_request_id=submit_request_id,
                is_closed=stage_handler.is_closed(),
            )

    except Exception as ex:
        traceback.print_stack()
        traceback.print_exc()
        return redirect(url_for("error", error_message=ex))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
