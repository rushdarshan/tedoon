from progressive_disclosure.pipeline import run_pipeline, _risk_tier


def generate_decision(form_state, tab_name):
    pipe = run_pipeline(form_state, tab_name)
    pd_median = pipe["pd"]
    lgd = pipe["lgd"]
    ecl = pipe["ecl"]
    risk_level = pipe["risk_level"]
    recommendation = pipe["recommendation"]
    ensemble = pipe["ensemble"]
    compliance = pipe["compliance"]
    base_pd = pipe["base_pd"]
    base_risk_level, base_recommendation = _risk_tier(base_pd)

    top_risk_factors = []
    if pd_median > 10:
        top_risk_factors.append(f"Elevated default probability ({pd_median:.1f}%)")
    if lgd > 40:
        top_risk_factors.append(f"High loss severity ({lgd:.1f}% LGD)")
    if not form_state.get("collateral_type") or str(form_state.get("collateral_type", "")).lower() == "none":
        top_risk_factors.append("No collateral coverage")
    for s in ensemble.get("shap_top5", [])[:2]:
        if abs(s["importance"]) > 0.01:
            top_risk_factors.append(f"{s['feature']} (SHAP: {s['importance']:+.3f})")

    return {
        "pd": pd_median,
        "lgd": lgd,
        "ecl": ecl,
        "risk_level": risk_level,
        "recommendation": recommendation,
        "top_risk_factors": top_risk_factors[:5],
        "baseline_pd": base_pd,
        "baseline_risk_level": base_risk_level,
        "baseline_recommendation": base_recommendation,
        "ensemble": ensemble,
        "compliance": compliance,
        "pipeline_stages": pipe["stages"],
    }
