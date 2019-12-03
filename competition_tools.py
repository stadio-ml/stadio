import datetime
import pandas as pd
import os
from enum import Enum
from evaluation_functions import evaluator

ALLOWED_EXTENSIONS = {'.csv'}
HEADER = ["Id", "Predicted"]
INDEX = "Id"
TARGET = "Predicted"
PUBLIC = "Public"

def check_file(file, test_file):
    try:
        test_df = pd.read_csv(test_file, index_col=INDEX)
    except Exception as ex:
        raise Exception(f"Test solution error - File: {test_file} - {ex}")

    submitted_df = pd.read_csv(file.stream, index_col=INDEX)
    submitted_columns = list(submitted_df.columns) + [INDEX] # "INDEX" is not included in .columns
    # check file schema
    if not (all([h in submitted_columns for h in HEADER]) == True):
        missing_cols = [h for h in HEADER if h not in submitted_columns]
        raise Exception(f"Missing columns {missing_cols} in the submitted solution with columns {submitted_columns}.")

    if len(submitted_columns) > len(HEADER):
        raise Exception(f"Too many columns - Expecting columns {HEADER} in submitted solution.")

    # check file len
    if len(submitted_df.index) != len(test_df.index):
        raise Exception(f"Submitted solution length does not match the dataset length. Submitted solution has {len(submitted_df.index)} rows while Dataset has {len(test_df.index)} rows.")

    # TODO: check file size

    # check indices
    if set(submitted_df.index) != set(test_df.index):
        raise Exception("Indices do not match!")

    return True

def eval_public_private(submission, solution):
    try:
        df_pred = pd.read_csv(submission, index_col=INDEX).sort_index()
        df_true = pd.read_csv(solution, index_col=INDEX).sort_index()
        assert len(df_pred) == len(df_true) # already checked, should be true!x
        assert (df_pred.index == df_true.index).all() # already checked, should be true!
    except Exception:
        # We shuld never fail here -- the file has already been validated!
        raise Exception("Unexpected error! Please contact an administrator")

    public_mask = df_true[PUBLIC] == 1
    y_pred_public = df_pred[public_mask][TARGET].values
    y_true_public = df_true[public_mask][TARGET].values

    y_pred_private = df_pred[~public_mask][TARGET].values
    y_true_private = df_true[~public_mask][TARGET].values
    
    public_score = evaluator(y_true_public, y_pred_public)
    private_score = evaluator(y_true_private, y_pred_private)
    
    return public_score, private_score

def allowed_file(filename):

    if not os.path.splitext(filename.lower())[1] in ALLOWED_EXTENSIONS:
        error_message = f'Unsupported file format. Allowed file formats are {ALLOWED_EXTENSIONS}'
        raise Exception(error_message)

    return True


def get_timestamp():
    timestamp_id = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%s")
    return timestamp_id


class Stage(Enum):
    READY = 0
    OPEN = 1
    CLOSED = 2
    TERMINATED = 3


class StageHandler:
    def __init__(self, open_time, close_time, terminate_time):
        self.open_time = datetime.datetime.strptime(open_time, "%Y/%m/%d %H:%M:%S")
        self.close_time = datetime.datetime.strptime(close_time, "%Y/%m/%d %H:%M:%S")
        self.terminate_time = datetime.datetime.strptime(terminate_time, "%Y/%m/%d %H:%M:%S")

        if self.close_time > self.terminate_time or self.open_time > self.close_time:
            raise RuntimeError('Competition dates order is wrong!')

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