from transport import admit_event


def render(raw_event):
    event = admit_event(raw_event)
    return "Transport error"
