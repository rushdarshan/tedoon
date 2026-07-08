import gradio as gr

FIELD_STATES = ("HIDDEN", "ASKING", "FILLED", "EDITED")
BATCH_SIZE = 5


def field_state_transition(state, field_key, new_state):
    if new_state not in FIELD_STATES:
        raise ValueError(f"Invalid field state: {new_state}. Must be one of {FIELD_STATES}")
    state[field_key] = new_state
    return state


def component_for_field(field_def, value=None, state="HIDDEN"):
    label = field_def["label"]
    ftype = field_def["type"]
    key = field_def["key"]

    kwargs = {"label": label, "key": key}

    if state == "HIDDEN":
        return gr.Column(visible=False)

    if state == "FILLED":
        kwargs["interactive"] = False
        kwargs["value"] = value
    elif state == "EDITED":
        kwargs["value"] = value
    elif state == "ASKING":
        pass

    if ftype == "str":
        return gr.Textbox(**kwargs)
    elif ftype == "float":
        return gr.Number(**kwargs)
    elif ftype == "int":
        return gr.Number(precision=0, **kwargs)
    elif ftype == "enum":
        return gr.Dropdown(choices=field_def.get("options", []), **kwargs)
    elif ftype == "bool":
        return gr.Checkbox(**kwargs)
    elif ftype == "date":
        kwargs["placeholder"] = "DD-MM-YYYY"
        return gr.Textbox(**kwargs)
    else:
        raise ValueError(f"Unknown field type: {ftype}")


def render_fields(field_defs, form_state, field_reveal):
    components = []
    for f in field_defs:
        key = f["key"]
        state = field_reveal.get(key, "HIDDEN")
        value = form_state.get(key)
        comp = component_for_field(f, value, state)
        components.append(comp)
    return components


def get_visible_fields(field_reveal):
    return [k for k, v in field_reveal.items() if v != "HIDDEN"]


def get_asking_fields(field_reveal):
    return [k for k, v in field_reveal.items() if v == "ASKING"]


def compute_next_batch(field_defs, form_state, field_reveal):
    to_reveal = []
    for f in field_defs:
        key = f["key"]
        if field_reveal.get(key, "HIDDEN") != "HIDDEN":
            continue
        if form_state.get(key):
            continue
        to_reveal.append(key)
        if len(to_reveal) >= BATCH_SIZE:
            break
    return to_reveal
