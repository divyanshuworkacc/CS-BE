from tests.helpers import add_product


def test_mark_then_list_then_unmark_toggles(
    client, make_admin, make_regular_user, login_as
):
    admin, tenant = make_admin()
    login_as(admin)
    product = add_product(client, tenant.name)

    user, _ = make_regular_user(tenant_name=tenant.name)
    login_as(user)

    resp = client.post(f"/favourites/{product['id']}")
    assert resp.status_code == 200

    favs = client.get("/favourites").json()
    assert any(p["id"] == product["id"] for p in favs)

    # calling the same endpoint again un-marks it (toggle behavior)
    resp = client.post(f"/favourites/{product['id']}")
    assert resp.status_code == 200

    favs = client.get("/favourites").json()
    assert all(p["id"] != product["id"] for p in favs)


def test_mark_unknown_product_404s(client, as_user):
    resp = client.post("/favourites/9999")
    assert resp.status_code == 404


def test_favourites_are_scoped_per_user(
    client, make_admin, make_regular_user, login_as
):
    admin, tenant = make_admin()
    login_as(admin)
    product = add_product(client, tenant.name)

    user_a, _ = make_regular_user(username="user_a", tenant_name=tenant.name)
    login_as(user_a)
    client.post(f"/favourites/{product['id']}")

    user_b, _ = make_regular_user(username="user_b", tenant_name=tenant.name)
    login_as(user_b)
    favs = client.get("/favourites").json()
    assert favs == []  # user_b never favourited anything
