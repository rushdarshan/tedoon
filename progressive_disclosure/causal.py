import numpy as np
import pandas as pd
from dowhy import CausalModel

from progressive_disclosure.synthetic_data import generate_msme_dataset, engineer_features

_DAG = """
digraph {
    years_in_operation -> turnover;
    turnover -> default;
    years_in_operation -> default;
    credit_score -> default;
    days_late -> default;
    cash_stress -> days_late;
    cash_stress -> credit_score;
    cash_stress -> default;
    cash_stress -> gst_regular;
    gst_regular -> default;
    buyer_conc -> default;
    suppliers -> default;
}
"""


def _prepare_data():
    df = generate_msme_dataset()
    X = engineer_features(df)
    dat = pd.DataFrame({
        "default": df["has_default"].values,
        "years_in_operation": X["years_in_operation"].values,
        "turnover": X["annual_turnover_log"].values,
        "credit_score": X["credit_score_norm"].values,
        "days_late": X["avg_days_late_norm"].values,
        "buyer_conc": X["buyer_concentration"].values,
        "suppliers": X["supplier_count_norm"].values,
        "gst_regular": 0,
    })
    gst_cols = [c for c in X.columns if c.startswith("gst_")]
    if "gst_Regular (monthly)" in gst_cols:
        dat["gst_regular"] = X["gst_Regular (monthly)"].values
    return dat.dropna()


def estimate_effect(treatment, outcome="default", data=None):
    if data is None:
        data = _prepare_data()
    common = ["years_in_operation", "turnover", "credit_score", "buyer_conc", "suppliers"]
    if treatment == "days_late":
        confounders = list(set(common + ["gst_regular"]))
        t = "days_late"
    elif treatment == "gst_regular":
        confounders = list(set(common + ["days_late"]))
        t = "gst_regular"
    else:
        return None

    model = CausalModel(
        data=data,
        treatment=t,
        outcome=outcome,
        common_causes=confounders,
    )
    identified = model.identify_effect(proceed_when_unidentifiable=True)
    estimate = model.estimate_effect(identified, method_name="backdoor.linear_regression")

    ref_placebo = model.refute_estimate(identified, estimate, "placebo_treatment", placebo_type="permute")
    ref_rand_cause = model.refute_estimate(identified, estimate, "random_common_cause")

    naive_diff = _naive_correlation(data, t, outcome)

    return {
        "treatment": treatment,
        "ate": estimate.value,
        "naive_correlation": naive_diff,
        "causal_gap": naive_diff - estimate.value if naive_diff is not None else None,
        "refutation": {
            "placebo_treatment": {
                "refute_estimate": ref_placebo.new_effect,
                "target": 0.0,
                "pass": abs(ref_placebo.new_effect) < 0.01,
            },
            "random_common_cause": {
                "refute_estimate": ref_rand_cause.new_effect,
                "target": estimate.value,
                "pass": abs(ref_rand_cause.new_effect - estimate.value) < 0.02,
            },
        },
    }


def _naive_correlation(data, treatment, outcome):
    if data[treatment].nunique() < 3:
        grouped = data.groupby(treatment)[outcome].mean()
        if len(grouped) >= 2 and 0 in grouped.index and 1 in grouped.index:
            return grouped.loc[1] - grouped.loc[0]
    else:
        return data[treatment].corr(data[outcome])


def run_causal_audit(form_state=None):
    results = {}
    for t in ["days_late", "gst_regular"]:
        try:
            r = estimate_effect(t)
            if r:
                results[t] = r
        except Exception as e:
            results[t] = {"error": str(e)}
    return results


def contrast_with_shap(causal_results, shap_top5):
    gst_shap = next((s["importance"] for s in shap_top5 if "gst" in s["feature"]), 0)
    late_shap = next((s["importance"] for s in shap_top5 if "late" in s["feature"]), 0)

    lines = []
    for t, name in [("days_late", "avg_days_late_norm"), ("gst_regular", "GST Regular")]:
        cr = causal_results.get(t, {})
        if "error" in cr:
            continue
        ate = cr.get("ate", 0)
        naive = cr.get("naive_correlation", 0)
        gap = cr.get("causal_gap", 0)
        shap_v = gst_shap if t == "gst_regular" else late_shap
        direction = "↓" if ate < 0 else "↑"
        lines.append(f"- **{name}**: Naïve Δ={naive:+.3f}, Causal ATE={ate:+.3f} {direction}, SHAP={shap_v:+.3f}, gap={gap:+.3f}")
        for rt, rd in cr.get("refutation", {}).items():
            chk = "✅" if rd.get("pass") else "⚠️"
            lines.append(f"  {chk} {rt}: expected={rd['target']:.3f}, got={rd['refute_estimate']:.3f}")
    return "\n".join(lines)
