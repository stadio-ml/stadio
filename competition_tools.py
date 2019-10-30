import datetime
import random
import string
import pandas as pd
import traceback

ALLOWED_EXTENSIONS = ('.csv')
HEADER = {"Id", "Predicted"}

def randomString(stringLength=8):
    """Generate a random string of fixed length """
    letters= string.ascii_lowercase
    return ''.join(random.sample(letters, stringLength))


def check_file(file, test_file):
    check = True

    try:

        test_df = pd.read_csv(test_file)
    except Exception as ex:
        raise Exception(f"Test solution error - File: {test_file} - {ex}")

    submitted_df = pd.read_csv(file.stream)
    # check file schema
    if not any(h in submitted_df.columns for h in HEADER):
        raise Exception(f"Missing columns {HEADER.difference(set(submitted_df.columns))} in submitted solution.")

    if len(submitted_df.columns) > 2:
        raise Exception(f"Too many columns - Expecting columns {HEADER} in submitted solution.")

    # check file len
    if len(submitted_df.index) != len(test_df.index):
        raise Exception(f"Submitted solution length does not match the dataset length. Submitted solution has {len(submitted_df.index)} rows while Dataset has {len(test_df.index)} rows.")

    # check file size

    return True


def allowed_file(filename):
    return filename.lower().endswith(ALLOWED_EXTENSIONS)


def get_timestamp():
    timestamp_id = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%s")
    return timestamp_id