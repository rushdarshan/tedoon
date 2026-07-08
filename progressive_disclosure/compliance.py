import hashlib, json
from datetime import datetime


MODEL_VERSION = "IDBI-ENSEMBLE-25-v1.0"


def _disparate_impact_ratio(shap_values, features):
    sector_idxs = [i for i, f in enumerate(features) if f.startswith("sector_")]
    if not sector_idxs or not shap_values:
        return "N/A (no sector features)"
    sector_shaps = [abs(shap_values[i]) for i in sector_idxs]
    return round(sum(sector_shaps) / len(sector_shaps), 4)


def generate_compliance_memo(form_state, result):
    pd_median = result.get("pd_median", 0)
    risk_level = result.get("risk_level", "Unknown")
    recommendation = result.get("recommendation", "Unknown")
    top5 = result.get("shap_top5", [])
    shap_vals = result.get("shap_values", [])
    features = result.get("features", [])

    audit_payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "model_version": MODEL_VERSION,
        "pd_median": pd_median,
        "risk_level": risk_level,
        "recommendation": recommendation,
        "top_shap_features": [s["feature"] for s in top5],
        "form_inputs": {k: v for k, v in form_state.items() if v},
    }
    audit_hash = hashlib.sha256(json.dumps(audit_payload, sort_keys=True).encode()).hexdigest()[:16]

    dir_ratio = _disparate_impact_ratio(shap_vals, features)

    is_rejection = recommendation.lower() in ("decline", "review with additional collateral")
    if is_rejection:
        top_factors_en = "\n".join(
            f"- {s['feature']}: {abs(s['importance']):.3f} (SHAP contribution)"
            for s in top5[:3]
        )
        notice_en = (
            f"ADVERSE ACTION NOTICE\n"
            f"Date: {datetime.utcnow().strftime('%Y-%m-%d')}\n"
            f"Model: {MODEL_VERSION}\n"
            f"Audit ID: {audit_hash}\n\n"
            f"Your application was {recommendation.lower()}. The key factors:\n"
            f"{top_factors_en}\n\n"
            f"You may request a detailed explanation within 60 days."
        )
        top_factors_hi = "\n".join(
            f"- {s['feature']}: {abs(s['importance']):.3f}"
            for s in top5[:3]
        )
        notice_hi = (
            f"प्रतिकूल कार्रवाई सूचना\n"
            f"दिनांक: {datetime.utcnow().strftime('%Y-%m-%d')}\n"
            f"मॉडल: {MODEL_VERSION}\n"
            f"ऑडिट आईडी: {audit_hash}\n\n"
            f"आपका आवेदन {recommendation.lower()} हुआ। प्रमुख कारण:\n"
            f"{top_factors_hi}\n\n"
            f"आप 60 दिनों के भीतर विस्तृत स्पष्टीकरण का अनुरोध कर सकते हैं।"
        )
    else:
        notice_en = None
        notice_hi = None

    return {
        "model_version": MODEL_VERSION,
        "audit_hash": audit_hash,
        "disparate_impact_ratio": dir_ratio,
        "notice_en": notice_en,
        "notice_hi": notice_hi,
        "is_rejection": is_rejection,
        "audit_payload": audit_payload,
    }


def format_memo_text(memo):
    lines = [
        "╔══════════════════════════════════════╗",
        "║    RBI MRMF COMPLIANCE MEMO          ║",
        "╚══════════════════════════════════════╝",
        f"Model: {memo['model_version']}",
        f"Audit ID: {memo['audit_hash']}",
        f"Disparate Impact Ratio: {memo['disparate_impact_ratio']}",
        f"Decision: {'REJECTION' if memo['is_rejection'] else 'APPROVAL'}",
        "",
    ]
    if memo["is_rejection"]:
        lines.append("--- ADVERSE ACTION NOTICE (English) ---")
        lines.append(memo["notice_en"])
        lines.append("")
        lines.append("--- ADVERSE ACTION NOTICE (Hindi) ---")
        lines.append(memo["notice_hi"])
    else:
        lines.append("Approval memo: No adverse action notice required.")
        lines.append("SHAP factor summary available upon request.")
    return "\n".join(lines)
