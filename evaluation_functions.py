"""
Use this module to set the evaluation fuction. 

- evaluator: the evaluation function used to assign scores
- evaluator_name: a plain name
- to_maximize: boolean used to sort properly the leaderboard
"""
from sklearn.metrics import accuracy_score


evaluator = accuracy_score
evaluator_name = "Accuracy"
to_maximize = True