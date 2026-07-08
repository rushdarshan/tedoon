import numpy as np
import pandas as pd
import os


def _assign_event(rng, profile):
    event_map = {
        "healthy":    [(0, 0.70), (2, 0.20), (3, 0.10)],
        "thin_file":  [(0, 0.50), (1, 0.20), (2, 0.15), (3, 0.15)],
        "stressed":   [(0, 0.15), (1, 0.55), (3, 0.30)],
        "fraudulent": [(0, 0.30), (1, 0.60), (2, 0.10)],
        "seasonal":   [(0, 0.55), (1, 0.15), (2, 0.10), (3, 0.20)],
    }
    events = event_map.get(profile, [(0, 1.0)])
    types, probs = zip(*events)
    return rng.choice(types, p=probs)


def _time_to_event(rng, event_type, profile):
    if event_type == 0:
        return rng.uniform(18, 36)
    base = {"healthy": 24, "thin_file": 18, "stressed": 10, "fraudulent": 14, "seasonal": 20}
    t = rng.exponential(base.get(profile, 18))
    return min(36, max(3, t))


def generate_msme_dataset(n=3000, seed=42):
    rng = np.random.default_rng(seed)
    records = []
    sectors = ["Manufacturing", "Services", "Retail", "Agriculture", "Construction", "IT/Technology"]
    biz_types = ["Sole Proprietorship", "Partnership", "Private Limited", "LLP"]

    profiles = {
        "healthy":    {"count": 1000, "pd_range": (0.5, 8.0)},
        "thin_file":  {"count": 600,  "pd_range": (3.0, 15.0)},
        "stressed":   {"count": 600,  "pd_range": (12.0, 35.0)},
        "fraudulent": {"count": 400,  "pd_range": (5.0, 20.0)},
        "seasonal":   {"count": 400,  "pd_range": (4.0, 18.0)},
    }

    for profile, spec in profiles.items():
        for _ in range(spec["count"]):
            sector = rng.choice(sectors)
            biz_type = rng.choice(biz_types)
            years = rng.integers(1, 30) if profile != "thin_file" else rng.integers(0, 5)
            turnover = rng.uniform(100000, 5e7) if profile != "thin_file" else rng.uniform(50000, 2e6)
            credit_score = int(rng.normal(700, 60))
            credit_score = max(350, min(900, credit_score))
            if profile == "healthy": credit_score = max(650, min(900, credit_score))
            if profile == "stressed": credit_score = min(650, credit_score)
            existing_loan = rng.uniform(0, turnover * 0.6) if rng.random() > 0.3 else 0.0
            gst_consistency = rng.choice(["Regular (monthly)", "Irregular", "New registrant", "Not registered"],
                                         p=[0.6, 0.15, 0.1, 0.15])
            if profile == "healthy": gst_consistency = "Regular (monthly)"
            if profile == "thin_file": gst_consistency = rng.choice(["New registrant", "Not registered", "Regular (monthly)"], p=[0.3, 0.3, 0.4])
            supplier_count = int(rng.integers(3, 50))
            buyer_concentration = rng.uniform(0.1, 0.9)
            avg_days_late = rng.exponential(5) if profile in ("stressed",) else rng.exponential(2)

            event_type = _assign_event(rng, profile)
            time_to_event = _time_to_event(rng, event_type, profile)

            rec = {
                "sector": sector,
                "business_type": biz_type,
                "years_in_operation": years,
                "annual_turnover": round(turnover, 2),
                "credit_score": credit_score,
                "existing_loan_amount": round(existing_loan, 2),
                "gst_filing_consistency": gst_consistency,
                "supplier_count": supplier_count,
                "buyer_concentration": round(buyer_concentration, 3),
                "avg_days_late": round(avg_days_late, 1),
                "profile": profile,
                "has_default": 1 if profile in ("stressed",) else 0,
                "is_fraud": 1 if profile == "fraudulent" else 0,
                "event_type": event_type,
                "time_to_event": round(time_to_event, 1),
            }
            records.append(rec)

    df = pd.DataFrame(records)
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    return df


def engineer_features(df):
    features = pd.DataFrame()
    features["years_in_operation"] = df["years_in_operation"]
    features["annual_turnover_log"] = np.log1p(df["annual_turnover"])
    features["credit_score_norm"] = df["credit_score"] / 900.0
    features["existing_loan_ratio"] = np.where(df["annual_turnover"] > 0, df["existing_loan_amount"] / df["annual_turnover"], 0)
    features["supplier_count_norm"] = np.log1p(df["supplier_count"])
    features["buyer_concentration"] = df["buyer_concentration"]
    features["avg_days_late_norm"] = np.log1p(df["avg_days_late"])
    sectors = pd.get_dummies(df["sector"], prefix="sector")
    gst = pd.get_dummies(df["gst_filing_consistency"], prefix="gst")
    biz = pd.get_dummies(df["business_type"], prefix="biz")
    features = pd.concat([features, sectors, gst, biz], axis=1)
    return features


def generate_and_save(output_dir="models"):
    os.makedirs(output_dir, exist_ok=True)
    df = generate_msme_dataset(3000)
    path = os.path.join(output_dir, "msme_synthetic_3000.csv")
    df.to_csv(path, index=False)
    print(f"[OK] Generated {len(df)} records -> {path}")
    return df


if __name__ == "__main__":
    generate_and_save()
