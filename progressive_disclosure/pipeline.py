import time

from progressive_disclosure.ensemble_model import predict_ensemble, predict_base_pd
from progressive_disclosure.compliance import generate_compliance_memo
from progressive_disclosure.competing_risks import get_model as get_cr_model


def _risk_tier(pd):
    if pd < 5: return "Low", "Approve"
    if pd < 12: return "Medium", "Approve with monitoring"
    if pd < 20: return "High", "Review with additional collateral"
    return "Very High", "Decline"


def run_pipeline(form_state, tab_name="PD"):
    stages = []

    t0 = time.time()
    ensemble = predict_ensemble(form_state)
    stages.append({"stage": "Ensemble Inference (25 models)", "duration_s": round(time.time() - t0, 3),
                   "detail": f"PD median={ensemble['pd_median']:.1f}%, P10={ensemble['pd_p10']:.1f}%, P90={ensemble['pd_p90']:.1f}%"})

    t0 = time.time()
    pd_median = ensemble["pd_median"]
    lgd = 45.0
    collateral = str(form_state.get("collateral_type", "")).lower() if form_state.get("collateral_type") else ""
    lgd -= {"property": 10, "fixed deposit": 15, "gold": 12, "inventory": 2}.get(collateral, 0)
    if collateral == "receivables": lgd += 5
    if collateral == "none": lgd += 20
    lgd = max(5.0, min(80.0, lgd))
    ead = float(form_state.get("ead_amount", 0) or 0) or float(form_state.get("loan_amount", 0) or 500000)
    ecl = round((pd_median / 100.0) * (lgd / 100.0) * ead, 2)
    risk_level, recommendation = _risk_tier(pd_median)
    stages.append({"stage": "Risk Tier + LGD + ECL", "duration_s": round(time.time() - t0, 3),
                   "detail": f"{risk_level} → {recommendation}, LGD={lgd:.1f}%, ECL=₹{ecl:,.0f}"})

    t0 = time.time()
    base_pd = predict_base_pd(form_state)
    base_risk_level, base_recommendation = _risk_tier(base_pd)
    stages.append({"stage": "Baseline (Simple Rules)", "duration_s": round(time.time() - t0, 3),
                   "detail": f"PD={base_pd:.1f}%, {base_risk_level} → {base_recommendation}"})

    t0 = time.time()
    compliance = generate_compliance_memo(form_state, {
        **ensemble, "risk_level": risk_level, "recommendation": recommendation,
    })
    stages.append({"stage": "Compliance Memo (RBI MRMF)", "duration_s": round(time.time() - t0, 3),
                   "detail": f"Audit {compliance['audit_hash']}, DIR={compliance['disparate_impact_ratio']}"})

    t0 = time.time()
    cr = get_cr_model().predict(form_state, horizons=[12])
    cif12 = cr["summary"]["12m"]
    stages.append({"stage": "Competing Risks (cause-specific Cox)", "duration_s": round(time.time() - t0, 3),
                   "detail": f"P(default)={cif12['default']:.1f}%, P(exit)={cif12['voluntary_exit']:.1f}%, P(restructure)={cif12['restructure']:.1f}%"})

    top_risk_factors = []
    if pd_median > 10:
        top_risk_factors.append(f"Elevated default probability ({pd_median:.1f}%)")
    if lgd > 40:
        top_risk_factors.append(f"High loss severity ({lgd:.1f}% LGD)")
    if not form_state.get("collateral_type") or collateral == "none":
        top_risk_factors.append("No collateral coverage")
    for s in ensemble.get("shap_top5", [])[:2]:
        if abs(s["importance"]) > 0.01:
            top_risk_factors.append(f"{s['feature']} (SHAP: {s['importance']:+.3f})")

    return {
        "recommendation": recommendation,
        "risk_level": risk_level,
        "pd": pd_median,
        "lgd": lgd,
        "ecl": ecl,
        "base_pd": base_pd,
        "compliance": compliance,
        "ensemble": ensemble,
        "top_risk_factors": top_risk_factors[:5],
        "competing_risks": cr,
        "stages": stages,
        "total_duration_s": round(sum(s["duration_s"] for s in stages), 3),
    }
