"""Reproducer: browsing the catalogue while the database is unreachable."""


def test_catalogue_is_unavailable(real_deps_client):
    assert real_deps_client.get("/products").status_code == 500
    assert real_deps_client.get("/health/live").status_code == 200
