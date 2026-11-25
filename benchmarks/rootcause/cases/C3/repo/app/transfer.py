from app.convert import convert


def transfer(src, dst, amount):
    converted = convert(amount, src.currency, dst.currency)
    src.withdraw(amount)
    dst.deposit(converted)
    return converted
