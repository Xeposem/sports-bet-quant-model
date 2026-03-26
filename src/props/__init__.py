"""Prop prediction model registry.

Maps stat_type strings to train/predict callables for each prop model.

Stat types:
  - aces: NegBin/Poisson GLM on ace count
  - double_faults: NegBin/Poisson GLM on double fault count
  - games_won: NegBin/Poisson GLM on total games won from score
  - breaks_of_serve: NegBin/Poisson GLM on bp_faced - bp_saved
  - sets_won: NegBin/Poisson GLM on sets won (best_of covariate, max_k=6)
  - first_set_winner: Logistic regression returning 2-element PMF

Usage:
    from src.props import PROP_REGISTRY

    trained = PROP_REGISTRY["aces"]["train"](conn)
    result  = PROP_REGISTRY["aces"]["predict"](trained, feature_row)
"""

from src.props.aces import train as aces_train, predict as aces_predict
from src.props.double_faults import train as df_train, predict as df_predict
from src.props.games_won import train as gw_train, predict as gw_predict
from src.props.breaks_of_serve import train as bos_train, predict as bos_predict
from src.props.sets_won import train as sw_train, predict as sw_predict
from src.props.first_set_winner import train as fsw_train, predict as fsw_predict

PROP_REGISTRY = {
    "aces":             {"train": aces_train,  "predict": aces_predict},
    "double_faults":    {"train": df_train,    "predict": df_predict},
    "games_won":        {"train": gw_train,    "predict": gw_predict},
    "breaks_of_serve":  {"train": bos_train,   "predict": bos_predict},
    "sets_won":         {"train": sw_train,    "predict": sw_predict},
    "first_set_winner": {"train": fsw_train,   "predict": fsw_predict},
}
