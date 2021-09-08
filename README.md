![](banner.png)

# Stadio

### Check list before running a competition
1. Create competition_folder, with:
    - eval_solution.csv
    - dump folder
    - uploads folder
    - mappings.tsv file
2. Update config.py
3. Update evaluation_function.py with evaluation function
4. Run the competition

### Setup
1. Create and activate a virtual environment with Python 3 (>= 3.6 recommended). E.g.
```bash
python3 -m venv /path/to/new/virtual/environment
source /path/to/new/virtual/environment/bin/activate
```

2. Install requirements
```
pip install -r requirements.txt
```

3. Init a new competition by creating the following structure
```
competition_files
├── eval_solution.csv  # ground truth and Public/Private information 
├── mappings.tsv       # file with the roaster and api keys
├── dumps/             # where to store the db dumps
└── uploads/           # where to store the file submitted by students
```

4. Edit the `config.py` file with the competition metadata

5. Edit the `evaluation_functions.py` file to set the evaluation function 

6. Launch the server
```
python3 WSGI.py
```

### Platform Configuration
Example configuration file:
```python
    NAME = 'Competition Name'

    # UTC TIME (YYYY/MM/DD HH:MM:SS)
    OPEN_TIME = '2020/11/18 16:00:00'
    CLOSE_TIME = '2020/11/25 00:00:01'
    TERMINATE_TIME = '2020/11/27 00:00:01'

    # USERS with special behaviours
    ADMIN_USER_ID = "name_of_admin_user"
    BASELINE_USER_ID = "name_of_baseline_user"

    # BASE directory where you might want to store all the competition data
    BASE_DIR = "path/to/competition_folder"

    # Folder in which every submission file is stored
    UPLOAD_FOLDER = join(BASE_DIR, "uploads")

    # Folder in which every database dump is stored
    DUMP_FOLDER = join(BASE_DIR, "dumps")

    # File with gold labels
    TEST_FILE_PATH = join(BASE_DIR, "eval_solution.csv")

    MAX_FILE_SIZE = 32 * 1024 * 1024  # limit upload file size to 32MB

    # File used to identify users on the platform
    API_FILE = join(BASE_DIR, "mappings.tsv")  # API mappings

    # The sqlite database for the current competition
    DB_FILE = "sqlite:///" + join(BASE_DIR, "competition_db_name.db")

    TIME_BETWEEN_SUBMISSIONS = 5 * 60  # 5 minutes between submissions
    MAX_NUMBER_SUBMISSIONS = 100
```

Competition STAGES:
- OPEN: the competition is started and all the user in the mapping file can submit a solution. Before the open date only `admin` and `baseline can submit.
- CLOSE: competition participants can still submit but the competition is closed and their score would not appear in the leader-boards
- TERMINATE: the competition is terminated and submissions are closed for everybody
Once the competition dates are set up they should not be changed, otherwise the dashboards could not work properly.


USERS with special behaviours:
- `ADMIN_USER_ID`: can access the dashboards and can submit at any time. His submission would not appear on any leader-board.
- `BASELINE_USER_ID`: can access the dashboards and can submit at any time. His submission would appear on all leader-board highlighted as baseline.

BASE directory: 
- `BASE_DIR` stores all the competition data
- `UPLOAD_FOLDER` stores all the participants submission files
- `DUMP_FOLDER` stores a dump of the `competition_db_name.db` at CLOSE and TERMINATE stages.
DSLE will automatically create the `competition_db_name.db` database in the BASE directory.`

MAPPINGS file:
- Only users specified in the MAPPINGS file can participate to the competition.
- Example mappings file at [mappings example](https://github.com/dbdmg/utilities/blob/main/utilities/mappings.dummy.tsv)

OTHER configuration options:
- `TIME_BETWEEN_SUBMISSIONS`: limits the frequency of submission per-participant. The value has to be specified in seconds.
- `MAX_NUMBER_SUBMISSIONS`: limits the number of submissions per-participant.

### Submission evaluation
The `eval_solution.csv` should contain the gold labels for the current competition (column *Predicted*) and a setting to specify whether the sample should be used for the public leaderbord, the private one, or both (column *Public*). Set the latter to `1` to use the record for the public leaderboard, to `0` to use it for the private one, or `2` for both.

The `eval_solution.csv` should have the following structure:
```csv
Id,Predicted,Public
0,0,0
1,0,1
2,0,0
3,1,1
4,1,0
5,1,0
```

The `evaluation_functions.py` contains the evaluation function that should be used for the competition.
- The `evaluator` attribute contains the function that should be used to evaluate the submissions. The evaluation function should be similar to: `evaluation_function(y_true: Any, y_pred: Any, **kwags)`
- The `evaluator_name` attribute contains the name of the evaluation function that would appear on the dashboard.
- The `to_maximize` attribute must be set to specify whether the score produced by the evaluator must be maximized or not (e.g. for *accuracy_score* it should set to `True`, while for *mean_absolute_error* it should be set to `False`)

### Available services
List of available APIs:
- `leaderboard`
- `fleaderboard`
- `submit`
- `dashboard_login`
- `dashboard_logout`
- `student_dasboard`
- `general_dasboard` 

The special users can access the private sections specifying the parameter `api_key` to each service if available. 

### Selecting the solutions to evaluate on DSLE
In the participant's private area they can choose at most 2 solutions to be evaluated.
DSLE gets the max private score among the selected solutions for the participants that have selected at least one solution.
Instead, DSLE gets the private score corresponding to the max public score for the people that did not select any solutions.

### Publications
If you are using the platform or if you are exploiting it in your research project please consider to cite the paper about this project:

```bibtex
@inproceedings{attanasio2020dsle,
  title={DSLE: A Smart Platform for Designing Data Science Competitions},
  author={Attanasio, Giuseppe and Giobergia, Flavio and Pasini, Andrea and Ventura, Francesco and Baralis, Elena and Cagliero, Luca and Garza, Paolo and Apiletti, Daniele and Cerquitelli, Tania and Chiusano, Silvia},
  booktitle={2020 IEEE 44th Annual Computers, Software, and Applications Conference (COMPSAC)},
  pages={133--142},
  year={2020},
  organization={IEEE}
}
```



