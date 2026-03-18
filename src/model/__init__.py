"""Model registry — maps version strings to train/predict callables."""

from src.model.logistic import train as logistic_train, predict as logistic_predict
from src.model.xgboost_model import train as xgb_train, predict as xgb_predict

MODEL_REGISTRY = {
    "logistic_v1": {"train": logistic_train, "predict": logistic_predict},
    "xgboost_v1":  {"train": xgb_train,      "predict": xgb_predict},
}
