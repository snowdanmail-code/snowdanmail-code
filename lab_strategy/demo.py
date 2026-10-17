"""Print a synthetic bluff-spot analysis. Nothing is sent to GPT/1win."""
from lab_strategy.engine import LabSpot,study_as_json
spot = LabSpot(pot=100, to_call=0, effective_stack=300, equity=.18,
    estimated_fold_probability=.65, opponents=1, position='late', street='turn',
    board_threat=.60, blocker_relevance=.7, villain_observations=100)
print(study_as_json(spot))
