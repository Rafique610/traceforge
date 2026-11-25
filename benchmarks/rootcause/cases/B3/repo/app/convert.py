from app.rates import lookup


def convert(amount, src, dst):
    return round(amount * lookup(src) / lookup(dst), 2)
