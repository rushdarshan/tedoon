---
title: Tedoon
emoji: 🏃
colorFrom: purple
colorTo: green
sdk: gradio
sdk_version: 6.20.0
python_version: '3.12'
app_file: app.py
pinned: false
license: mit
short_description: MSME credit risk — ensemble PD, competing risks Cox, cascade contagion, fair lending auditscade contagion
---

# Tedoon — IDBI MSME Risk Assessment

**IDBI Innovate 2026 — Track 04 entry.** End-to-end MSME credit risk pipeline: fuzzy input → risk decision in ~1 second.

## What it does

Conversational chat UI fills a credit assessment form from a plain-English description. Once fields are complete, the pipeline runs:

**5 tabs — PD / LGD / ECL / Cascade / Report —** each with its own field set and model:

| Tab | Inputs | Output |
|-----|--------|--------|
| **PD** | Sector, turnover, years, CIBIL, GST | Ensemble PD (25 models), SHAP drivers |
| **LGD** | Loan amount, collateral, seniority | Loss Given Default estimate |
| **ECL** | PD/LGD estimates, exposure, scenario | Expected Credit Loss |
| **Cascade** | Supplier count, buyer concentration | Contagion exposure score |
| **Report** | Name, PAN, address | Decision memo + audit hash (RBI MRMF) |

The pipeline chains: 25-model LightGBM ensemble → competing-risks Cox model (default/exit/restructure) → baseline rule comparison → compliance memo (fair lending audit, SHAP feature attribution).

## Quick start

```bash
pip install -r requirements.txt
export GOOGLE_API_KEY="your-gemini-key"
python app.py
```

Then open the Gradio URL. Type something like:

> *MSME in textiles, ₹50L turnover, been in business 8 years*

The chat fills the form. Once complete, results render inline.

**No API key?** A rule-based parser handles common MSME descriptions (sector, turnover, years, CIBIL, GST, business type) without any LLM call.

## Project structure

```
app.py                          # Gradio entry — 5 tabs
progressive_disclosure/
├── fields.py                   # Field definitions per tab (17 fields, 5 types)
├── engine.py                   # LLM + rule-based field extraction
├── form_renderer.py            # Dynamic form state machine (HIDDEN→ASKING→FILLED→EDITED)
├── app.py                      # Chat + form shell, decision flow
├── models.py                   # Model loading + decision generation
├── pipeline.py                 # Orchestrates ensemble → LGD/ECL → compliance → competing risks
├── ensemble_model.py           # 25-model LightGBM ensemble
├── competing_risks.py          # Cause-specific Cox model (default / exit / restructure)
├── compliance.py               # Fair lending audit (disparate impact, RBI MRMF)
├── calibration.py              # Score calibration + plotting
├── synthetic_data.py           # Synthetic MSME data generation
├── train_model.py              # Model training pipeline
└── causal.py                   # Causal inference (DoWhy)
docs/
├── brainstorms/                # Requirements docs
└── ideation/                   # Strategy research, constraint-flipping ideas
```

## Tech stack

- **UI:** Gradio 6 (5 tabs, chat + dynamic form, 2-column layout)
- **LLM:** Gemini 2.0 Flash (rule fallback if no API key)
- **Models:** LightGBM (25-model ensemble), lifelines (Cox PH)
- **Explainability:** SHAP, DoWhy (causal inference)
- **Compliance:** RBI MRMF fair lending audit, disparate impact ratio
- **Hardware target:** RTX 4050 (local training), HF Spaces (demo)

## Pipeline per decision

```
User text → rule/LLM extract → form revealed → all required filled →
  1. Ensemble PD (25 LightGBM models)     → PD median + P10/P90
  2. LGD (collateral-adjusted) + ECL      → Expected loss
  3. Baseline rules comparison            → Simple-model benchmark
  4. Competing risks Cox                  → Default / exit / restructure probability
  5. Compliance memo (RBI MRMF)          → Audit hash, fair lending DI ratio
  6. Top risk factors (SHAP)             → Feature attribution
```

## Environment variables

- `GOOGLE_API_KEY` — Gemini API key for LLM-based field extraction
- `DEBUG=1` — Prints full LLM prompts and raw responses to stderr
