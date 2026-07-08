import gradio as gr

from progressive_disclosure.engine import process_llm_input, get_missing_fields
from progressive_disclosure.form_renderer import compute_next_batch, field_state_transition
from progressive_disclosure.fields import TAB_FIELDS
from progressive_disclosure.models import generate_decision
from progressive_disclosure.calibration import run_calibration


_CAL_RESULT = None


def _load_calibration():
    global _CAL_RESULT
    if _CAL_RESULT is None:
        try:
            _CAL_RESULT = run_calibration()
        except Exception:
            _CAL_RESULT = None


def _render_form_html(field_defs, form_state, field_reveal, phase, progress_text, results=None):
    rows = ""
    for pf in sorted_fields_from_defs(field_defs):
        key = pf["key"]
        state = field_reveal.get(key, "HIDDEN")
        value = form_state.get(key, "")

        if state == "HIDDEN" and phase != "done":
            continue

        label = pf["label"]
        req = '*' if pf["required"] else ''
        
        if state == "HIDDEN":
            row = f'<div class="field-hidden" style="display:none">{label}</div>'
        elif state == "ASKING":
            row = f'''<div class="field-asking">
                <div class="field-label">{label}{req}</div>
                <div class="field-input"><em style="color:#888">— awaiting your input —</em></div>
            </div>'''
        elif state == "FILLED":
            display_val = value if value else ""
            row = f'''<div class="field-filled">
                <div class="field-label">{label}{req}</div>
                <div class="field-value" onclick="alert('Type your correction in the chat')">{display_val}</div>
            </div>'''
        elif state == "EDITED":
            display_val = value if value else ""
            row = f'''<div class="field-edited">
                <div class="field-label">{label}{req} <span class="edited-badge">edited</span></div>
                <div class="field-value">{display_val}</div>
            </div>'''

        rows += row

    if not rows:
        rows = '<div style="color:#888; padding: 12px;">Your fields will appear here as we talk.</div>'

    progress = f'<div class="progress-bar">{progress_text}</div>' if progress_text else ''

    results_html = ""
    if results:
        base_pd = results.get("baseline_pd")
        color = "#43a047" if results["risk_level"] in ("Low", "Medium") else "#e53935"
        base_color = "#43a047" if results.get("baseline_risk_level", "Medium") in ("Low", "Medium") else "#e53935"
        factors = "".join(f"<li>{f}</li>" for f in results.get("top_risk_factors", []))
        delta = results["pd"] - base_pd if base_pd else 0
        delta_str = f"{delta:+.1f}pp" if base_pd and abs(delta) > 0.1 else "0.0pp"
        delta_color = "#43a047" if delta < 0 else "#e53935"

        ensemble = results.get("ensemble", {})
        p10 = ensemble.get("pd_p10", results["pd"])
        p90 = ensemble.get("pd_p90", results["pd"])
        spread = ensemble.get("spread", 0)
        conew = 260
        cone_left = max(0, min(conew, int((p10 / 40.0) * conew)))
        cone_mid = max(0, min(conew, int((results["pd"] / 40.0) * conew)))
        cone_right = max(0, min(conew, int((p90 / 40.0) * conew)))
        cone_span = max(4, cone_right - cone_left)

        compliance = results.get("compliance", {})
        audit_hash = compliance.get("audit_hash", "")
        is_rejection = compliance.get("is_rejection", False)

        stages = results.get("pipeline_stages", [])
        stages_html = ""
        if stages:
            rows = "".join(
                f'<tr><td style="padding:2px 6px;font-size:11px;">{s["stage"]}</td>'
                f'<td style="padding:2px 6px;font-size:11px;text-align:right;color:#888;">{s["duration_s"]*1000:.0f}ms</td></tr>'
                for s in stages
            )
            stages_html = f"""
            <div class="results-box" style="border-color:#78909c;margin-top:8px;">
                <h4 style="margin:0 0 4px 0;font-size:13px;">Pipeline Stages</h4>
                <table style="width:100%;">{rows}</table>
                <div style="margin-top:4px;font-size:11px;color:#888;text-align:right;">Total: {sum(s["duration_s"] for s in stages)*1000:.0f}ms</div>
            </div>"""

        _load_calibration()
        cal_badge = ""
        if _CAL_RESULT:
            cal = _CAL_RESULT
            dir_icon = "✅" if cal["post_ece"] < 0.05 else "⚠️"
            cal_badge = f'<span style="font-size:10px;color:#888;margin-left:8px;">{dir_icon} Cal: Brier={cal["post_brier"]:.4f} ECE={cal["post_ece"]:.4f} T={cal["T_optimal"]:.2f}</span>'

        results_html = f"""
        <div style="margin-top:8px;">
            <div style="display:flex; gap:12px; margin-bottom:8px;">
                <div class="results-box" style="border-color:{color}; flex:1;">
                    <h4 style="margin:0 0 6px 0; color:{color};">Crack Propagation Velocity</h4>
                    <table style="width:100%; font-size:13px;">
                        <tr><td><strong>Decision</strong></td><td style="color:{color};font-weight:600;">{results['recommendation']}</td></tr>
                        <tr><td><strong>Crack Velocity</strong></td><td style="color:{color};">{results['risk_level']}</td></tr>
                        <tr><td><strong>PD</strong></td><td>{results['pd']:.1f}%</td></tr>
                        <tr><td><strong>LGD</strong></td><td>{results['lgd']:.1f}%</td></tr>
                        <tr><td><strong>ECL</strong></td><td>₹{results['ecl']:,.0f}</td></tr>
                    </table>
                </div>
                <div class="results-box" style="border-color:{base_color}; flex:1; background:#f5f5f5;">
                    <h4 style="margin:0 0 6px 0; color:{base_color};">Baseline (Simple Rules)</h4>
                    <table style="width:100%; font-size:13px;">
                        <tr><td><strong>Decision</strong></td><td style="color:{base_color};font-weight:600;">{results.get('baseline_recommendation','N/A')}</td></tr>
                        <tr><td><strong>Risk</strong></td><td style="color:{base_color};">{results.get('baseline_risk_level','N/A')}</td></tr>
                        <tr><td><strong>PD</strong></td><td>{base_pd:.1f}%</td></tr>
                        <tr><td><strong>AI Advantage</strong></td><td style="color:{delta_color};font-weight:600;">{delta_str}</td></tr>
                    </table>
                    <div style='margin-top:6px;font-size:11px;color:#888;'>{'✅ AI more conservative' if delta < 0 else '⚠️ AI sees nuance baseline misses' if delta > 0.5 else '✓ AI agrees with baseline'}</div>
                </div>
            </div>
            <div class="results-box" style="border-color:#5c6bc0;">
                <h4 style="margin:0 0 6px 0;">Cone of Uncertainty (25-model ensemble)</h4>
                <div style="position:relative; height:30px; background:#f0f0f0; border-radius:4px; margin:4px 0;">
                    <div style="position:absolute; left:{cone_left}px; width:{cone_span}px; height:30px; background:rgba(92,107,192,0.25); border-radius:4px;"></div>
                    <div style="position:absolute; left:{cone_mid}px; width:4px; height:30px; background:{color}; border-radius:2px;"></div>
                    <div style="position:absolute; left:{cone_left}px; top:32px; font-size:10px; color:#888;">P10: {p10:.1f}%</div>
                    <div style="position:absolute; left:{cone_right - 30}px; top:32px; font-size:10px; color:#888;">P90: {p90:.1f}%</div>
                    <div style="position:absolute; left:{cone_mid - 10}px; top:-14px; font-size:10px; font-weight:600; color:{color};">{results['pd']:.1f}%</div>
                </div>
                <div style="margin-top:18px; font-size:11px; color:#666;">Spread: {spread:.1f}pp {'(highly confident)' if spread < 5 else '(moderate uncertainty)' if spread < 12 else '(wide uncertainty)'} &mdash; {ensemble.get('ensemble_size', 25)} models</div>
            </div>
            <div style="display:flex; gap:12px; margin-top:8px;">
                <div class="results-box" style="border-color:#5c6bc0; flex:2;">
                    <h4 style="margin:0 0 6px 0;">Risk Factor Dashboard</h4>
                    <ul style="margin:4px 0 0 0; padding-left:16px; font-size:13px;">{factors}</ul>
                </div>
                <div class="results-box" style="border-color:{'#e53935' if is_rejection else '#43a047'}; flex:1;">
                    <h4 style="margin:0 0 4px 0; font-size:13px;">RBI MRMF Compliance</h4>
                    <div style="font-size:11px;">
                        <div>Audit: <code style="font-size:10px;">{audit_hash}</code></div>
                        <div>Model: {compliance.get('model_version','N/A')}</div>
                        <div>DIR: {compliance.get('disparate_impact_ratio','N/A')}</div>
                        <div style="margin-top:4px; color:{'#e53935' if is_rejection else '#43a047'}; font-weight:600;">
                    {'⚠️ Adverse action notice generated' if is_rejection else '✓ Compliant'}
                        </div>
                    </div>
                </div>
                cr = results.get("competing_risks", {})
                cr_html = ""
                cif12 = cr.get("summary", {}).get("12m", {})
                if cif12:
                    cr_html = f"""
                    <div class="results-box" style="border-color:#7b1fa2;margin-top:8px;">
                        <h4 style="margin:0 0 4px 0;font-size:13px;">Competing Risks (12-month CIF)</h4>
                        <table style="width:100%;font-size:12px;">
                            <tr><td>P(Default)</td><td style="font-weight:600;color:#e53935;">{cif12['default']:.1f}%</td></tr>
                            <tr><td>P(Voluntary Exit)</td><td style="font-weight:600;color:#fb8c00;">{cif12['voluntary_exit']:.1f}%</td></tr>
                            <tr><td>P(Restructure)</td><td style="font-weight:600;color:#1565c0;">{cif12['restructure']:.1f}%</td></tr>
                            <tr><td>Total Event Risk</td><td style="font-weight:600;">{cif12['total_event']:.1f}%</td></tr>
                        </table>
                    </div>"""
                {stages_html}
                {cal_badge}
            </div>"""

    return f"""
    <style>
        .field-asking {{ background: #fff8e1; border-left: 3px solid #f9a825; padding: 8px 12px; margin: 6px 0; border-radius: 4px; }}
        .field-filled {{ background: #e8f5e9; border-left: 3px solid #43a047; padding: 8px 12px; margin: 6px 0; border-radius: 4px; cursor: pointer; }}
        .field-edited {{ background: #e3f2fd; border-left: 3px solid #1e88e5; padding: 8px 12px; margin: 6px 0; border-radius: 4px; }}
        .field-label {{ font-weight: 600; font-size: 13px; margin-bottom: 4px; }}
        .field-value {{ font-size: 14px; }}
        .edited-badge {{ font-size: 10px; color: #1e88e5; font-weight: 400; }}
        .progress-bar {{ background: #e3f2fd; padding: 6px 12px; border-radius: 4px; margin-bottom: 8px; font-size: 13px; }}
        .form-panel {{ padding: 4px; }}
        .summary-box {{ background: #f1f8e9; border: 1px solid #8bc34a; padding: 12px; border-radius: 6px; margin-top: 8px; }}
        .results-box {{ background: #e8eaf6; border: 1px solid #5c6bc0; padding: 12px; border-radius: 6px; margin-top: 8px; }}
    </style>
    <div class="form-panel">
        {progress}
        {rows}
        {results_html}
    </div>
    """


def sorted_fields_from_defs(field_defs):
    return sorted(field_defs, key=lambda f: (0 if f["required"] else 1, f.get("priority", 0)))


def _build_initial_state(tab_name):
    return {
        "form_state": {},
        "field_reveal": {},
        "phase": "active",
        "tab_name": tab_name,
        "summary": "",
    }


def respond(message, history, state):
    state = dict(state)
    tab_name = state.get("tab_name", "PD")
    field_defs = TAB_FIELDS.get(tab_name, [])
    form_state = dict(state.get("form_state", {}))
    field_reveal = dict(state.get("field_reveal", {}))
    phase = state.get("phase", "active")

    if phase == "done":
        return "", history, _render_form_html(field_defs, form_state, field_reveal, "done", ""), state

    if not message.strip():
        return "", history, _render_form_html(field_defs, form_state, field_reveal, phase, ""), state

    user_msg = message.strip()
    history.append({"role": "user", "content": user_msg})

    if phase == "confirming":
        if user_msg.lower() in ("yes", "lock in", "confirm", "y", "lock"):
            state["phase"] = "done"
            state["results"] = generate_decision(form_state, tab_name)
            results = state["results"]
            risk_color = "🟢" if results["risk_level"] in ("Low", "Medium") else "🔴"
            factors = "\n".join(f"- {f}" for f in results.get("top_risk_factors", []))
            ensemble = results.get("ensemble", {})
            p10 = ensemble.get("pd_p10", 0)
            p90 = ensemble.get("pd_p90", 0)
            spread = ensemble.get("spread", 0)
            cone_line = f"**Cone:** P10={p10:.1f}% | Median={results['pd']:.1f}% | P90={p90:.1f}% (spread: {spread:.1f}pp)" if p10 else ""
            baseline_section = ""
            if results.get("baseline_pd") is not None:
                delta = results["pd"] - results["baseline_pd"]
                baseline_section = (
                    f"\n**Comparative Baseline:**\n"
                    f"- Simple rules model PD: {results['baseline_pd']:.1f}%\n"
                    f"- AI advantage: {delta:+.1f}pp vs rule-based\n\n"
                )
            compliance = results.get("compliance", {})
            compliance_line = f"\n**RBI MRMF Memo:** Audit {compliance.get('audit_hash','')} | DIR: {compliance.get('disparate_impact_ratio','N/A')}"
            decision_msg = (
                f"✅ **Application processed!**\n\n"
                f"{risk_color} **Decision:** {results['recommendation']}\n"
                f"**Crack Velocity:** {results['risk_level']}\n"
                f"**PD:** {results['pd']:.1f}% | **LGD:** {results['lgd']:.1f}% | **ECL:** ₹{results['ecl']:,.0f}\n\n"
                f"{cone_line}\n\n"
                f"**Key Drivers:**\n{factors}\n\n"
                f"{baseline_section}"
                f"{compliance_line}\n\n"
                f"---\n*Start a new tab or reset to begin again.*"
            )
            history.append({"role": "assistant", "content": decision_msg})
            html = _render_form_html(field_defs, form_state, field_reveal, "done", "", results=results)
            return "", history, html, state
        else:
            history.append({"role": "assistant", "content": "Type 'lock in' to confirm, or edit any field by typing the correction."})
            html = _render_form_html(field_defs, form_state, field_reveal, "confirming", "")
            return "", history, html, state

    if phase == "active" and not field_reveal:
        types_text = ""
        for f in field_defs:
            opts = f" ({', '.join(f['options'])})" if f.get("options") else ""
            types_text += f"  - {f['label']}{' *' if f['required'] else ''}{opts}\n"
        greeting = (
            "Welcome! Tell me about your business and I'll help fill out the form. "
            "For example: *'MSME in textiles with ₹50L annual turnover, been in business 8 years.'*\n\n"
            "I need the following information:\n"
            f"{types_text}"
        )
        history.append({"role": "assistant", "content": greeting})
        html = _render_form_html(field_defs, form_state, field_reveal, "active", "")
        return "", history, html, state

    result = process_llm_input(user_msg, form_state, field_defs)

    for k, v in result.get("filled_fields", {}).items():
        if field_reveal.get(k) != "EDITED" and v:
            form_state[k] = v
            field_state_transition(field_reveal, k, "FILLED")

    missing = get_missing_fields(form_state, field_reveal, tab_name)

    if not missing:
        state["phase"] = "confirming"
        summary = result.get("summary", "All fields have been filled.")
        state["summary"] = summary
        history.append({"role": "assistant", "content": f"{summary}\n\n---\n✅ All required fields are complete. Type **'lock in'** to confirm and process."})
        html = _render_form_html(field_defs, form_state, field_reveal, "confirming", "✅ All fields complete — ready to lock in")
    else:
        next_batch = compute_next_batch(field_defs, form_state, field_reveal)
        for key in next_batch:
            field_state_transition(field_reveal, key, "ASKING")
        next_q = result.get("next_question", "Could you tell me about the next field?")
        total = len([f for f in field_defs])
        done = len([k for k, v in field_reveal.items() if v in ("FILLED", "EDITED")])
        progress_text = f"Field {done} of {total} — next: {missing[0] if missing else ''}"
        state["summary"] = result.get("summary", "")
        history.append({"role": "assistant", "content": next_q})
        html = _render_form_html(field_defs, form_state, field_reveal, "active", progress_text)

    state["form_state"] = form_state
    state["field_reveal"] = field_reveal

    return "", history, html, state


def reset_fn(state):
    tab_name = state.get("tab_name", "PD")
    return [], _build_initial_state(tab_name), _render_form_html(TAB_FIELDS.get(tab_name, []), {}, {}, "active", "")


def create_app(tab_name="PD"):
    field_defs = TAB_FIELDS.get(tab_name, [])
    initial_state = _build_initial_state(tab_name)

    with gr.Blocks(title=f"IDBI Risk Assessment — {tab_name}") as app:
        gr.Markdown(f"# 🏦 IDBI MSME Risk Assessment — {tab_name}")
        gr.Markdown("⚠️ Session data is not saved. Do not close this tab.")

        chatbot = gr.Chatbot(label="Conversation", height=420, type="messages")
        msg = gr.Textbox(
            label="Your message",
            placeholder="Describe your business or answer the question...",
        )

        with gr.Row():
            submit_btn = gr.Button("Send", variant="primary", scale=2)
            reset_btn = gr.Button("Reset", variant="secondary", scale=1)

        form_display = gr.HTML(
            value=_render_form_html(field_defs, {}, {}, "active", ""),
        )

        state = gr.State(initial_state)

        msg.submit(respond, [msg, chatbot, state], [msg, chatbot, form_display, state])
        submit_btn.click(respond, [msg, chatbot, state], [msg, chatbot, form_display, state])

        reset_btn.click(reset_fn, state, [chatbot, state, form_display])

    return app


if __name__ == "__main__":
    app = create_app("PD")
    app.launch()
