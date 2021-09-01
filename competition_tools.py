import datetime
import sys
import threading

import pandas as pd
import os
from enum import Enum
from evaluation_functions import evaluator
from sqlalchemy import inspect, func
from config import CompetitionConfig
import numpy as np

from models import Submission, Evaluation

ALLOWED_EXTENSIONS = {".csv"}

INDEX = "Id"
TARGET = "Predicted"
PUBLIC = "Public"

HEADER = [INDEX, TARGET]
SOLUTION_HEADER = [INDEX, TARGET, PUBLIC]

# function that maps db-stored score to printable value
# TODO: move somewhere appropriate
score_mapper = lambda score: f"{score :.3f}"


def get_user_scores(db, user_id, maximized_score=True):
    participants = (
        db.session.query(
            Submission.user_id,
            Submission.timestamp,
            Evaluation.evaluation_public,
            Evaluation.evaluation_private,
        )
        .join(Submission)
        .filter(Submission.user_id == user_id)
        .order_by(
            Evaluation.evaluation_public.desc()
            if maximized_score
            else Evaluation.evaluation_public
        )
        .all()
    )

    participants = [
        (user_id, time, score_mapper(pub_score), score_mapper(priv_score))
        for user_id, time, pub_score, priv_score in participants
    ]
    return participants


def get_public_leaderboard(db, maximized_score=True):
    participants = (
        db.session.query(
            Submission.user_id,
            func.max(Evaluation.evaluation_public)
            if maximized_score
            else func.min(Evaluation.evaluation_public),
        )
        .join(Submission)
        .group_by(Submission.user_id)
        .order_by(
            Evaluation.evaluation_public.desc()
            if maximized_score
            else Evaluation.evaluation_public
        )
        .all()
    )

    participants = [(user_id, score_mapper(score)) for user_id, score in participants]
    return participants


def get_private_leaderboard(db, stage_handler, maximized_score=True):
    participants = list()

    # Get the max private score corresponding to the people that have selected at least one solution
    participants_select = (
        db.session.query(
            Submission.user_id,
            func.max(Evaluation.evaluation_private)
            if maximized_score
            else func.min(Evaluation.evaluation_private),
        )
        .join(Submission)
        .filter(
            Submission.timestamp < stage_handler.close_time,
            Evaluation.private_check.is_(True),
        )
        .group_by(Submission.user_id)
        .order_by(
            Evaluation.evaluation_private.desc()
            if maximized_score
            else Evaluation.evaluation_private
        )
        .all()
    )

    participants += participants_select

    # Get the people that did not select any solutions sorted by user_id, evaluation_public and timestamp
    participants_not_select = (
        db.session.query(
            Submission.user_id,
            Evaluation.evaluation_public,
            Evaluation.evaluation_private,
        )
        .join(Submission)
        .filter(
            Submission.timestamp < stage_handler.close_time,
            Submission.user_id.notin_([u_id for u_id, _ in participants_select]),
        )
        .order_by(
            Submission.user_id.desc(),
            Evaluation.evaluation_public.desc()
            if maximized_score
            else Evaluation.evaluation_public,
            Submission.timestamp.desc(),
        )
        .all()
    )

    # Get the private score corresponding to the max public score for the people that did not select any solutions
    # Since data is sorted desc, the first entry for each user is the score to take
    u_placeholder = set()
    for pns in participants_not_select:
        if pns[0] not in u_placeholder:
            participants.append((pns[0], pns[2]))
        u_placeholder.add(pns[0])

    # Sort the scores
    participants = sorted(participants, key=lambda x: x[1], reverse=maximized_score)
    participants = [(user_id, score_mapper(score)) for user_id, score in participants]

    return participants


def get_peruser_submissions_number(db):
    peruser_submission_count = (
        db.session.query(Submission.user_id, func.count(Submission.user_id))
        .filter(Submission.user_id != CompetitionConfig.ADMIN_USER_ID)
        .group_by(Submission.user_id)
        .all()
    )  # this result contains the baseline scores
    return peruser_submission_count


def get_user_submissions_number(user_id, db):
    submission_count = (
        db.session.query(func.count(Evaluation.submission_id))
        .join(Submission)
        .filter(Submission.user_id.is_(user_id))
        .scalar()
    )
    return submission_count


def get_submissions_number(db):
    submission_count = db.session.query(func.count(Evaluation.submission_id)).scalar()
    return submission_count


def check_solution_file(solution_file):
    print(f"Checking solution file '{solution_file}'...")
    try:
        solution_df = pd.read_csv(solution_file, index_col=INDEX)
        solution_columns = list(solution_df.columns) + [INDEX]
        # check file schema
        if not (all([h in solution_columns for h in SOLUTION_HEADER]) == True):
            missing_cols = [h for h in SOLUTION_HEADER if h not in solution_columns]
            raise Exception(
                f"Missing columns {missing_cols} in the solution file with columns {solution_columns}."
            )

        if len(solution_columns) > len(SOLUTION_HEADER):
            raise Exception(
                f"Too many columns - Expecting columns {SOLUTION_HEADER} in the solution file."
            )

        if (~solution_df[PUBLIC].isin([0, 1, 2])).any():
            raise Exception(
                f"Public column should contains only 0, 1 or 2 where:\n - 1 means public\n - 0 means private\n - 2 means both public and private"
            )

    except Exception as ex:
        raise Exception(f"Test solution error - File: {solution_file} - {ex}")

    print(f"Solution file is valid.")
    return True


def check_file(file, test_file):
    try:
        test_df = pd.read_csv(test_file, index_col=INDEX)
    except Exception as ex:
        raise Exception(f"Test solution error - File: {test_file} - {ex}")

    submitted_df = pd.read_csv(file.stream, index_col=INDEX)
    submitted_columns = list(submitted_df.columns) + [
        INDEX
    ]  # "INDEX" is not included in .columns
    # check file schema
    if not (all([h in submitted_columns for h in HEADER]) == True):
        missing_cols = [h for h in HEADER if h not in submitted_columns]
        raise Exception(
            f"Missing columns {missing_cols} in the submitted solution with columns {submitted_columns}."
        )

    if len(submitted_columns) > len(HEADER):
        raise Exception(
            f"Too many columns - Expecting columns {HEADER} in submitted solution."
        )

    # check file len
    if len(submitted_df.index) != len(test_df.index):
        raise Exception(
            f"Submitted solution length does not match the dataset length. Submitted solution has {len(submitted_df.index)} rows while Dataset has {len(test_df.index)} rows."
        )

    # TODO: check file size

    # check indices
    if set(submitted_df.index) != set(test_df.index):
        raise Exception("Indices do not match!")

    return True


def eval_public_private(submission, solution):
    try:
        df_pred = pd.read_csv(submission, index_col=INDEX).sort_index()
        df_true = pd.read_csv(solution, index_col=INDEX).sort_index()
        assert len(df_pred) == len(df_true)  # already checked, should be true!x
        assert (
            df_pred.index == df_true.index
        ).all()  # already checked, should be true!
    except Exception:
        # We should never fail here -- the file has already been validated!
        raise Exception("Unexpected error! Please contact an administrator")

    public_mask = (df_true[PUBLIC] == 1) | (df_true[PUBLIC] == 2)
    y_pred_public = df_pred[public_mask][TARGET].values
    y_true_public = df_true[public_mask][TARGET].values

    private_mask = (df_true[PUBLIC] == 0) | (df_true[PUBLIC] == 2)
    y_pred_private = df_pred[private_mask][TARGET].values
    y_true_private = df_true[private_mask][TARGET].values

    public_score = evaluator(y_true_public, y_pred_public)
    private_score = evaluator(y_true_private, y_pred_private)

    return public_score, private_score


def allowed_file(filename):

    if not os.path.splitext(filename.lower())[1] in ALLOWED_EXTENSIONS:
        error_message = (
            f"Unsupported file format. Allowed file formats are {ALLOWED_EXTENSIONS}"
        )
        raise Exception(error_message)

    return True


def get_timestamp():
    timestamp_id = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%s")
    return timestamp_id


def schedule_db_dump(sched_time, db, stage_name, dump_out):

    if not os.path.isdir(dump_out):
        print(f"Dump folder '{dump_out}' not exist! Create it!")
        sys.exit(-1)

    now = datetime.datetime.utcnow()

    parsed_sched_time = datetime.datetime.strptime(sched_time, "%Y/%m/%d %H:%M:%S")
    delay = (parsed_sched_time - now).total_seconds()

    def dumb_db_dump(db, stage_name, dump_out):
        dump_time = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        inspector = inspect(db.engine)

        for t_name in inspector.get_table_names():
            dest_path = os.path.join(
                dump_out, f"{t_name}_{stage_name}_{dump_time}_dump.csv"
            )

            print(f"Loading table '{t_name}'...")
            t_df = pd.read_sql_table(t_name, con=db.engine)

            print(f"Dumping {t_name} to {dest_path}")
            t_df.to_csv(dest_path, index=False)

    if delay > 0:
        threading.Timer(
            delay,
            dumb_db_dump,
            kwargs={"db": db, "stage_name": stage_name, "dump_out": dump_out},
        ).start()
        print(f"Scheduled DB dump in {delay} seconds for stage {stage_name}.")
    else:
        print("DB dump not scheduled. Negative delay!")


class Stage(Enum):
    READY = 0
    OPEN = 1
    CLOSED = 2
    TERMINATED = 3


class StageHandler:
    def __init__(self, open_time, close_time, terminate_time):
        self.open_time = datetime.datetime.strptime(open_time, "%Y/%m/%d %H:%M:%S")
        self.close_time = datetime.datetime.strptime(close_time, "%Y/%m/%d %H:%M:%S")
        self.terminate_time = datetime.datetime.strptime(
            terminate_time, "%Y/%m/%d %H:%M:%S"
        )

        if self.close_time > self.terminate_time or self.open_time > self.close_time:
            raise RuntimeError("Competition dates order is wrong!")

    def _get_stage(self):
        now = datetime.datetime.utcnow()
        stage = Stage.TERMINATED
        if now < self.terminate_time:
            stage = Stage.CLOSED
        if now < self.close_time:
            stage = Stage.OPEN
        if now < self.open_time:
            stage = Stage.READY
        return stage

    def is_ready(self):
        return self._get_stage() == Stage.READY

    def is_open(self):
        return self._get_stage() == Stage.OPEN

    def is_closed(self):
        return self._get_stage() == Stage.CLOSED

    def is_terminated(self):
        return self._get_stage() == Stage.TERMINATED

    def can_submit(self):
        stage = self._get_stage()
        return stage == Stage.OPEN or stage == Stage.CLOSED
