"""Prop prediction model registry.

Maps stat_type strings to train/predict callables for each prop model.

Usage:
    from src.props import PROP_REGISTRY

    trained = PROP_REGISTRY["aces"]["train"](conn)
    result  = PROP_REGISTRY["aces"]["predict"](trained, feature_row)
"""

from src.props.aces import train as aces_train, predict as aces_predict
from src.props.double_faults import train as df_train, predict as df_predict
from src.props.games_won import train as gw_train, predict as gw_predict

PROP_REGISTRY = {
    "aces":          {"train": aces_train,  "predict": aces_predict},
    "double_faults": {"train": df_train,    "predict": df_predict},
    "games_won":     {"train": gw_train,    "predict": gw_predict},
}
