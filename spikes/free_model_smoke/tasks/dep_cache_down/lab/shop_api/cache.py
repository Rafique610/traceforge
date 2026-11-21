"""Product catalogue reads through a Redis cache."""


def get_product(client, product_id):
    cached = client.get(f"product:{product_id}")
    if cached is not None:
        return cached
    row = {"id": product_id}
    client.set(f"product:{product_id}", row)
    return row
