from os.path import join


class CompetitionConfig:
    NAME = 'Lab #'

    # UTC TIME (YYYY/MM/DD HH:MM:SS)
    OPEN_TIME = '2019/12/02 11:25:00'
    CLOSE_TIME = '2020/02/08 08:26:00'
    TERMINATE_TIME = '2020/12/02 11:27:00'

    # USERS with special behaviours
    ADMIN_USER_ID = "prof"
    BASELINE_USER_ID = "baseline"

    # BASE directory where you might want to store all the completition data
    BASE_DIR = "base_dir"

    # Folder in which every submission file is stored
    UPLOAD_FOLDER = join(BASE_DIR, "uploads")

    # Folder in which every database dump is stored
    DUMP_FOLDER = join(BASE_DIR, "dumps")

    # File with gold labels
    TEST_FILE_PATH = join(BASE_DIR, "test_solution.csv")

    MAX_FILE_SIZE = 32 * 1024 * 1024  # limit upload file size to 32MB

    # File used to identify users on the platform
    API_FILE = join(BASE_DIR, "mappings.dummy.json")  # API mappings

    # The sqlite database for the current competition
    DB_FILE = join(BASE_DIR, "sqlite:///test.db")

    TIME_BETWEEN_SUBMISSIONS = 5 * 60  # 5 minutes between submissions
    MAX_NUMBER_SUBMISSIONS = 100
