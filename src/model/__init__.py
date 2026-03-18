"""Model registry -- maps version strings to train/predict callables."""

from src.model.logistic import train as logistic_train, predict as logistic_predict
from src.model.xgboost_model import train as xgb_train, predict as xgb_predict
from src.model.ensemble import train as ensemble_train, predict as ensemble_predict


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
    "logistic_v1": {"train": logistic_train,          "predict": logistic_predict},
    "xgboost_v1":  {"train": xgb_train,               "predict": xgb_predict},
    "bayesian_v1": {"train": _lazy_bayesian_train,     "predict": _lazy_bayesian_predict},
    "ensemble_v1": {"train": ensemble_train,           "predict": ensemble_predict},
}
