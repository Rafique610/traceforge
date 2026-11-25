from app.util import normalize


def parse_qty(text):
    return int(normalize(text)) + 1
