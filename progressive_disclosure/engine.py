import json
import os
import sys
import time

from google import genai

from progressive_disclosure.fields import TAB_FIELDS

FALLBACK_QUESTION = "I had trouble processing that. Let me ask directly — what is your {label}?"


def _build_prompt(user_text, current_state, field_defs):
    field_desc = ""
    for f in field_defs:
        required = "(required)" if f["required"] else "(optional)"
        options = f" Options: {', '.join(f['options'])}." if f.get("options") else ""
        current_val = current_state.get(f["key"])
        val_str = f" Current value: {current_val}." if current_val else ""
        field_desc += f"  - {f['key']}: {f['label']} ({f['type']}, {required}){options}{val_str}\n"

    system_prompt = (
        "You are a loan application assistant for MSME credit assessment. "
        "You have access to the following form fields:\n"
        f"{field_desc}\n"
        "Extract as many field values as you can from the user's input. "
        "Return ONLY valid JSON with these keys:\n"
        "  - filled_fields: dict of field_key -> inferred value for fields you can fill from the input\n"
        "  - missing_fields: list of field_key strings for fields still empty or ambiguous\n"
        "  - next_question: a natural language question in English asking for the most critical missing field. "
        "If you can fill multiple fields at once, do so and ask about the next important one.\n"
        "  - summary: a one-sentence summary of what you understand so far\n"
        "If the user contradicts a previously provided value, flag it in next_question and do not update filled_fields for that key.\n"
        "Output ONLY valid JSON. No markdown. No backticks."
    )
    return system_prompt, user_text


def _parse_response(response_text, field_defs):
    valid_keys = {f["key"] for f in field_defs}
    type_map = {f["key"]: f["type"] for f in field_defs}

    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    data = json.loads(text)

    filled = {}
    for k, v in data.get("filled_fields", {}).items():
        if k not in valid_keys:
            continue
        field_type = type_map.get(k)
        if field_type == "float":
            try:
                v = float(v)
            except (ValueError, TypeError):
                v = ""
        elif field_type == "int":
            try:
                v = int(v)
            except (ValueError, TypeError):
                v = ""
        filled[k] = v

    missing = [k for k in data.get("missing_fields", []) if k in valid_keys]

    return {
        "filled_fields": filled,
        "missing_fields": missing,
        "next_question": data.get("next_question", ""),
        "summary": data.get("summary", ""),
    }


def _fallback_response(field_defs):
    first_required = None
    missing_keys = []
    for f in sorted(field_defs, key=lambda x: x["priority"]):
        if f["required"]:
            if first_required is None:
                first_required = f
            missing_keys.append(f["key"])
    question = FALLBACK_QUESTION.format(label=first_required["label"]) if first_required else "Could you describe your application?"
    return {
        "filled_fields": {},
        "missing_fields": missing_keys,
        "next_question": question,
        "summary": "",
    }


def process_llm_input(user_text, current_state, field_defs):
    if not user_text.strip():
        return _fallback_response(field_defs)

    if len(user_text) > 2000:
        user_text = user_text[:2000]

    system_prompt, user_prompt = _build_prompt(user_text, current_state, field_defs)

    if os.environ.get("DEBUG") == "1":
        print("=== SYSTEM PROMPT ===", file=sys.stderr)
        print(system_prompt, file=sys.stderr)
        print("=== USER PROMPT ===", file=sys.stderr)
        print(user_prompt, file=sys.stderr)

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set. Set it to your Gemini API key.")

    client = genai.Client(api_key=api_key)

    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[system_prompt, user_prompt],
                config={
                    "max_output_tokens": 1024,
                    "temperature": 0.1,
                },
                timeout=5,
            )
            raw = response.text
            if os.environ.get("DEBUG") == "1":
                print("=== RAW LLM RESPONSE ===", file=sys.stderr)
                print(raw, file=sys.stderr)
            return _parse_response(raw, field_defs)
        except json.JSONDecodeError:
            if attempt == 0:
                user_prompt = "Output ONLY valid JSON. No markdown. No backticks.\n\n" + user_prompt
                continue
            return _fallback_response(field_defs)
        except Exception:
            if attempt == 0:
                time.sleep(1)
                continue
            return _fallback_response(field_defs)

    return _fallback_response(field_defs)


def get_missing_fields(form_state, field_reveal, tab_name):
    field_defs = TAB_FIELDS.get(tab_name, [])
    missing = []
    for f in sorted(field_defs, key=lambda x: x["priority"]):
        key = f["key"]
        if f["required"] and not form_state.get(key):
            if field_reveal.get(key) not in ("FILLED", "EDITED"):
                missing.append(key)
    return missing


if __name__ == "__main__":
    from progressive_disclosure.fields import TAB_FIELDS

    pd_fields = TAB_FIELDS["PD"]
    test_input = "MSME in textiles, annual turnover of ₹50 lakh, been in business for 8 years"
    result = process_llm_input(test_input, {}, pd_fields)
    print(json.dumps(result, indent=2))
