import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import expit, logit

from progressive_disclosure import ensemble_model as em
from progressive_disclosure.synthetic_data import generate_msme_dataset, engineer_features


def _predict_batch(m, X):
    return m.predict_proba(X)[:, 1]


def _batch_ensemble_probs(df):
    em._lazy_load()
    X = engineer_features(df)
    for col in em.FEATURES:
        if col not in X.columns:
            X[col] = 0.0
    X = X[em.FEATURES]
    from joblib import Parallel, delayed
    probs = np.array(Parallel(n_jobs=-1, prefer="threads")(
        delayed(_predict_batch)(m, X) for m in em.MODELS
    ))
    return probs.T


def _reliability_data(probs, outcomes, n_bins=10):
    bins = np.linspace(0, 1, n_bins + 1)
    centers = (bins[:-1] + bins[1:]) / 2
    counts = np.zeros(n_bins)
    positives = np.zeros(n_bins)
    for i in range(n_bins):
        m = (probs >= bins[i]) & (probs < bins[i + 1])
        counts[i] = m.sum()
        if m.sum() > 0:
            positives[i] = outcomes[m].sum()
    observed = np.where(counts > 0, positives / counts, 0)
    return {"bin_centers": centers.tolist(), "observed_freq": observed.tolist(), "bin_counts": counts.tolist()}


def _expected_calibration_error(probs, outcomes, n_bins=10):
    edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        m = (probs >= edges[i]) & (probs < edges[i + 1])
        if m.sum() > 0:
            ece += (m.sum() / len(probs)) * abs(probs[m].mean() - outcomes[m].mean())
    return ece


def _brier_score(probs, outcomes):
    return float(np.mean((probs - outcomes) ** 2))


def _temperature_nll(T, logits, targets):
    eps = 1e-12
    cal = expit(logits / T)
    return -float(np.mean(targets * np.log(cal + eps) + (1 - targets) * np.log(1 - cal + eps)))


def run_calibration(n_profiles=500, holdout_frac=0.2):
    df = generate_msme_dataset(n_profiles + 100)
    df = df.head(n_profiles).reset_index(drop=True)
    all_raw = _batch_ensemble_probs(df)

    n_train = int(n_profiles * (1 - holdout_frac))
    train_raw, test_raw = all_raw[:n_train], all_raw[n_train:]

    train_pred = train_raw.mean(axis=1)
    test_pred = test_raw.mean(axis=1)

    rng = np.random.default_rng(42)
    train_outcomes = (rng.random(len(train_pred)) < train_pred).astype(float)
    test_outcomes = (rng.random(len(test_pred)) < test_pred).astype(float)

    pre_brier = _brier_score(test_pred, test_outcomes)
    pre_ece = _expected_calibration_error(test_pred, test_outcomes)
    pre_rel = _reliability_data(test_pred, test_outcomes)

    train_logits = logit(np.clip(train_pred, 1e-7, 1 - 1e-7))
    res = minimize_scalar(_temperature_nll, args=(train_logits, train_outcomes), bounds=(0.1, 10.0), method="bounded")
    T_opt = res.x

    test_logits = logit(np.clip(test_pred, 1e-7, 1 - 1e-7))
    test_calibrated = expit(test_logits / T_opt)

    post_brier = _brier_score(test_calibrated, test_outcomes)
    post_ece = _expected_calibration_error(test_calibrated, test_outcomes)
    post_rel = _reliability_data(test_calibrated, test_outcomes)

    return {
        "T_optimal": round(T_opt, 4),
        "pre_brier": round(pre_brier, 5),
        "post_brier": round(post_brier, 5),
        "pre_ece": round(pre_ece, 5),
        "post_ece": round(post_ece, 5),
        "n_profiles": n_profiles,
        "n_models": len(em.MODELS),
        "pre_reliability": pre_rel,
        "post_reliability": post_rel,
    }
