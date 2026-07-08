import os, json, pickle, joblib
import numpy as np
import pandas as pd
import lightgbm as lgb
import shap

from progressive_disclosure.synthetic_data import generate_msme_dataset, engineer_features


def train_ensemble(n_bootstrap=25, output_dir="models"):
    os.makedirs(output_dir, exist_ok=True)

    df = generate_msme_dataset(3000)
    X = engineer_features(df)
    y = df["has_default"].values
    feature_names = list(X.columns)

    base_params = {
        "objective": "binary", "metric": "auc", "n_estimators": 200,
        "max_depth": 4, "learning_rate": 0.08, "num_leaves": 16,
        "min_child_samples": 20, "verbosity": -1, "random_state": 42,
    }
    base_model = lgb.LGBMClassifier(**base_params)
    base_model.fit(X, y)
    base_auc = float(base_model.predict_proba(X)[:, 1].std())

    models = []
    rng = np.random.default_rng(42)
    for i in range(n_bootstrap):
        idx = rng.integers(0, len(X), size=len(X))
        Xb, yb = X.iloc[idx], y[idx]
        m = lgb.LGBMClassifier(**{**base_params, "random_state": 42 + i})
        m.fit(Xb, yb)
        models.append(m)

    explainer = shap.TreeExplainer(base_model)

    artifacts = {
        "feature_names": feature_names,
        "base_auc": base_auc,
        "n_bootstrap": n_bootstrap,
    }
    joblib.dump(models, os.path.join(output_dir, "ensemble_models.pkl"))
    joblib.dump(base_model, os.path.join(output_dir, "base_model.pkl"))
    joblib.dump(explainer, os.path.join(output_dir, "shap_explainer.pkl"))
    with open(os.path.join(output_dir, "artifacts.json"), "w") as f:
        json.dump(artifacts, f)

    print(f"[OK] Trained {n_bootstrap}-model ensemble, AUC std={base_auc:.4f}")
    print(f"[OK] Artifacts saved to {output_dir}/")
    return models, explainer, feature_names


if __name__ == "__main__":
    train_ensemble()
