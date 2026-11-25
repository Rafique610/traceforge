def _paid(order):
    return order["total"]


def _refund(order):
    return order["total"]


HANDLERS = {"paid": _paid, "refund": _refund}


def handle(event):
    return HANDLERS[event["kind"]](event["order"])
