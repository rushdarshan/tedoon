import os, json
import numpy as np
import pandas as pd
import joblib
from joblib import Parallel, delayed

np.seterr(invalid="ignore")


def _load_artifacts(model_dir="models"):
    models = joblib.load(os.path.join(model_dir, "ensemble_models.pkl"))
    explainer = joblib.load(os.path.join(model_dir, "shap_explainer.pkl"))
    base = joblib.load(os.path.join(model_dir, "base_model.pkl"))
    with open(os.path.join(model_dir, "artifacts.json")) as f:
        meta = json.load(f)
    return models, explainer, base, meta["feature_names"]


MODELS, EXPLAINER, BASE, FEATURES = None, None, None, None


def _lazy_load():
    global MODELS, EXPLAINER, BASE, FEATURES
    if MODELS is None:
        MODELS, EXPLAINER, BASE, FEATURES = _load_artifacts()


def form_state_to_features(form_state):
    sector = str(form_state.get("sector", "")).lower() if form_state.get("sector") else ""
    years = float(form_state.get("years_in_operation", 0) or 0)
    turnover = float(form_state.get("annual_turnover", 0) or 0)
    credit_score = float(form_state.get("credit_score", 700) or 700)
    existing_loan = float(form_state.get("existing_loan_amount", 0) or 0)
    gst = str(form_state.get("gst_filing_consistency", "Regular (monthly)") or "Regular (monthly)")
    biz = str(form_state.get("business_type", "Partnership") or "Partnership")
    suppliers = float(form_state.get("supplier_count", 10) or 10)
    buyer_conc = float(form_state.get("buyer_concentration", 0.3) or 0.3)
    avg_late = float(form_state.get("avg_days_late", 2) or 2)

    data = {
        "years_in_operation": years,
        "annual_turnover_log": np.log1p(turnover),
        "credit_score_norm": credit_score / 900.0,
        "existing_loan_ratio": existing_loan / max(turnover, 1),
        "supplier_count_norm": np.log1p(suppliers),
        "buyer_concentration": buyer_conc,
        "avg_days_late_norm": np.log1p(avg_late),
    }
    sectors = ["sector_Agriculture", "sector_Construction", "sector_IT/Technology",
               "sector_Manufacturing", "sector_Retail", "sector_Services"]
    for s in sectors:
        data[s] = 1.0 if s.split("_", 1)[1].lower() == sector else 0.0
    gsts = ["gst_Irregular", "gst_New registrant", "gst_Not registered", "gst_Regular (monthly)"]
    for g in gsts:
        data[g] = 1.0 if g.split("_", 1)[1] == gst else 0.0
    bizs = ["biz_LLP", "biz_Partnership", "biz_Private Limited", "biz_Sole Proprietorship"]
    for b in bizs:
        data[b] = 1.0 if b.split("_", 1)[1] == biz else 0.0

    df = pd.DataFrame([data])
    for col in FEATURES:
        if col not in df.columns:
            df[col] = 0.0
    return df[FEATURES]


def _predict_one(m, X):
    return m.predict_proba(X)[0, 1]


def predict_ensemble(form_state):
    _lazy_load()
    X = form_state_to_features(form_state)

    probs = np.array(Parallel(n_jobs=-1, prefer="threads")(delayed(_predict_one)(m, X) for m in MODELS))
    SCALE = 12.0
    median_pd = min(35.0, float(np.median(probs)) * 100 * SCALE)
    p10 = min(35.0, float(np.percentile(probs, 10)) * 100 * SCALE)
    p90 = min(35.0, float(np.percentile(probs, 90)) * 100 * SCALE)
    spread = p90 - p10

    shap_values = EXPLAINER.shap_values(X)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]
    shap_vals = shap_values[0]

    feat_imp = sorted(zip(FEATURES, shap_vals), key=lambda x: -abs(x[1]))
    top5 = [{"feature": f, "importance": round(float(v), 4)} for f, v in feat_imp[:5]]

    return {
        "pd_median": round(median_pd, 2),
        "pd_p10": round(p10, 2),
        "pd_p90": round(p90, 2),
        "spread": round(spread, 2),
        "ensemble_size": len(MODELS),
        "shap_top5": top5,
        "shap_values": shap_vals.tolist(),
        "features": list(X.columns),
    }


def predict_base_pd(form_state):
    _lazy_load()
    X = form_state_to_features(form_state)
    prob = float(BASE.predict_proba(X)[0, 1])
    return round(prob * 100 * 12.0, 2)
