from app import settings


def fee(amount):
    return round(amount * settings.FEE_RATE, 2)


def fee_inclusive(amount):
    return round(amount + fee(amount), 2)
