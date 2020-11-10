import json
import pandas as pd


class ApiAuth:
    def __init__(self, roster_file):
        self.roster_df = pd.read_csv(
            roster_file,
            sep="\t",
            header=0,
            dtype=dict(
                student_id=object, last_name=object, email=object, private_key=object
            ),
        )
        self.mapping = {
            student_id: api_key
            for student_id, api_key in zip(
                self.roster_df.student_id, self.roster_df.private_key
            )
        }
        self.reverse_mapping = {v: k for k, v in self.mapping.items()}

    def is_valid_key(self, api_key):
        return api_key in self.reverse_mapping

    def is_valid_user(self, user):
        return user in self.mapping

    def get_user(self, api_key):
        return self.reverse_mapping.get(api_key, None)

    def get_api_key(self, user):
        return self.mapping.get(user, None)
