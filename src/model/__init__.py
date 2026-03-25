"""Model registry -- maps version strings to train/predict callables."""

from src.model.logistic import train as logistic_train, predict as logistic_predict
from src.model.xgboost_model import train as xgb_train, predict as xgb_predict
from src.model.ensemble import (
    train as ensemble_train,
    predict as ensemble_predict,
    train_pinnacle as ensemble_pinnacle_train,
    predict_pinnacle as ensemble_pinnacle_predict,
    train_v3 as ensemble_v3_train,
    predict_v3 as ensemble_v3_predict,
)


# Lazy wrappers for bayesian_v1 -- PyMC imports PyTensor on load (~2-3s).
# Using lazy wrappers here means `from src.model import MODEL_REGISTRY` does NOT
# trigger a PyMC import. Only calling MODEL_REGISTRY["bayesian_v1"]["train"](...)
# will import PyMC (the first time it is needed).

def _lazy_bayesian_train(conn, config=None):
    from src.model.bayesian import train
    return train(conn, config)


def _lazy_bayesian_predict(trained, features, surface_idx=None):
    from src.model.bayesian import predict
    return predict(trained, features, surface_idx)


MODEL_REGISTRY = {
    "logistic_v1":         {"train": logistic_train,          "predict": logistic_predict},
    "xgboost_v1":          {"train": xgb_train,               "predict": xgb_predict},
    "bayesian_v1":         {"train": _lazy_bayesian_train,     "predict": _lazy_bayesian_predict},
    "ensemble_v1":         {"train": ensemble_train,           "predict": ensemble_predict},
    # Pinnacle-augmented versions: same train/predict functions as base versions.
    # LOGISTIC_FEATURES and XGB_FEATURES now include pinnacle_prob_diff + has_no_pinnacle,
    # so these labels serve as tracking identifiers for pinnacle-trained runs.
    "logistic_v3_pinnacle":  {"train": logistic_train,           "predict": logistic_predict},
    "xgboost_v2_pinnacle":   {"train": xgb_train,                "predict": xgb_predict},
    # Pinnacle ensemble: blends logistic_v3_pinnacle + xgboost_v2_pinnacle via inverse Brier
    "ensemble_v2_pinnacle":  {"train": ensemble_pinnacle_train,  "predict": ensemble_pinnacle_predict},
    # CSI-augmented versions: include court_speed_index, has_no_csi, speed_affinity_diff features
    "logistic_v4":    {"train": logistic_train,      "predict": logistic_predict},
    "xgboost_v3":     {"train": xgb_train,           "predict": xgb_predict},
    "ensemble_v3":    {"train": ensemble_v3_train,   "predict": ensemble_v3_predict},
}
