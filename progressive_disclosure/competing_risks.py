import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from lifelines import AalenJohansenFitter

from progressive_disclosure.synthetic_data import generate_msme_dataset, engineer_features


_EVENT_LABELS = {1: "Default", 2: "Voluntary Exit", 3: "Restructure"}
_TIME_HORIZONS = [6, 12, 18, 24, 36]


class CompetingRisksModel:
    def __init__(self):
        self.cause_models = {}
        self._pop_cifs = {}
        self._fitted = False

    def fit(self, df=None):
        if df is None:
            df = generate_msme_dataset()
        d, e = df["time_to_event"], df["event_type"]
        for cause in [1, 2, 3]:
            aj = AalenJohansenFitter(calculate_variance=False)
            aj.fit(d, event_observed=e, event_of_interest=cause)
            self._pop_cifs[cause] = aj.cumulative_density_

        for cause in [1, 2, 3]:
            c = df.copy()
            c["E_cause"] = (c["event_type"] == cause).astype(int)
            X = engineer_features(c)
            surv = pd.DataFrame({"T": c["time_to_event"], "E": c["E_cause"]})
            data = pd.concat([surv, X], axis=1)
            cph = CoxPHFitter(penalizer=0.01)
            cph.fit(data, duration_col="T", event_col="E", show_progress=False)
            self.cause_models[cause] = cph

        self._fitted = True
        return self

    @property
    def _feature_names(self):
        for cph in self.cause_models.values():
            return [c for c in cph.params_.index]
        return []

    def predict(self, form_state, horizons=None):
        if not self._fitted:
            self.fit()
        if horizons is None:
            horizons = _TIME_HORIZONS

        X_row = pd.DataFrame([form_state])
        X_feat = engineer_features(X_row)
        for col in self._feature_names:
            if col not in X_feat.columns:
                X_feat[col] = 0.0
        X_feat = X_feat[self._feature_names]

        cif_results = {}
        for cause in [1, 2, 3]:
            cph = self.cause_models[cause]
            hr = np.exp(cph.predict_log_partial_hazard(X_feat).values[0])
            pop_vals = self._pop_cifs[cause].iloc[:, 0]
            cif_vals = {}
            for t in horizons:
                nearest_idx = pop_vals.index.searchsorted(t)
                if nearest_idx >= len(pop_vals):
                    nearest_idx = len(pop_vals) - 1
                pop_prob = pop_vals.iloc[nearest_idx]
                cif_vals[t] = round(float(1 - (1 - pop_prob) ** hr) * 100, 2)
            cif_results[cause] = cif_vals

        summary = {}
        for t in horizons:
            total = sum(cif_results[c].get(t, 0) for c in cif_results)
            summary[f"{t}m"] = {
                "default": cif_results.get(1, {}).get(t, 0),
                "voluntary_exit": cif_results.get(2, {}).get(t, 0),
                "restructure": cif_results.get(3, {}).get(t, 0),
                "total_event": round(min(total, 100.0), 2),
            }

        return {"cif_by_cause": cif_results, "summary": summary, "horizons": horizons}


_MODEL = None


def get_model():
    global _MODEL
    if _MODEL is None:
        _MODEL = CompetingRisksModel().fit()
    return _MODEL
