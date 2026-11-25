from app import settings


class Stock:
    def __init__(self):
        self.items = {}

    def add(self, sku, qty):
        self.items[sku] = self.available(sku) + qty

    def available(self, sku):
        return self.items.get(sku, 0)

    def reserve(self, sku, qty):
        if qty > settings.MAX_QTY:
            raise ValueError("qty above limit")
        if qty > self.available(sku):
            raise ValueError("insufficient stock")
        self.items[sku] = self.available(sku) - qty
