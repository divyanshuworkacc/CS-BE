from app import models
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


def test_favourites_are_sorted_before_pagination(
    client, make_admin, make_regular_user, login_as, db_session
):
    admin, tenant = make_admin()
    login_as(admin)
    budget = add_product(client, tenant.name, name="Budget favourite", price=10)
    middle = add_product(client, tenant.name, name="Middle favourite", price=100)
    other = models.Tenant(name="second-brand")
    db_session.add(other)
    db_session.commit()
    premium = add_product(client, other.name, name="Premium favourite", price=1000)

    user, _ = make_regular_user()
    login_as(user)
    for product_id in (budget["id"], middle["id"], premium["id"]):
        assert client.post(f"/favourites/{product_id}").status_code == 200

    first_page = client.get("/favourites", params={"sort": "price-high", "limit": 1})
    second_page = client.get(
        "/favourites", params={"sort": "price-high", "skip": 1, "limit": 1}
    )

    assert [product["name"] for product in first_page.json()] == ["Premium favourite"]
    assert [product["name"] for product in second_page.json()] == ["Middle favourite"]


def test_favourites_support_product_filters(
    client, make_admin, make_regular_user, login_as
):
    admin, tenant = make_admin()
    login_as(admin)
    def create_product(name, category):
        response = client.post(
            f"/{tenant.name}/products",
            json={"name": name, "category": category, "quantity": 10, "price": 50},
        )
        return response.json()

    matching = create_product("Air Max favourite", "footwear")
    non_matching_name = create_product("Classic Tee", "footwear")
    non_matching_category = create_product("Air Max shirt", "apparel")

    user, _ = make_regular_user()
    login_as(user)
    for product_id in (
        matching["id"],
        non_matching_name["id"],
        non_matching_category["id"],
    ):
        assert client.post(f"/favourites/{product_id}").status_code == 200

    response = client.get(
        "/favourites", params={"search": "Air", "category": "footwear"}
    )

    assert [product["id"] for product in response.json()] == [matching["id"]]


def test_favourites_can_be_filtered_by_brand(
    client, make_admin, make_regular_user, login_as, db_session
):
    admin, first_tenant = make_admin()
    second_tenant = models.Tenant(name="second-brand")
    db_session.add(second_tenant)
    db_session.commit()

    login_as(admin)
    first_product = add_product(client, first_tenant.name, name="First brand product")
    second_product = add_product(
        client, second_tenant.name, name="Second brand product"
    )

    user, _ = make_regular_user()
    login_as(user)
    for product_id in (first_product["id"], second_product["id"]):
        assert client.post(f"/favourites/{product_id}").status_code == 200

    response = client.get("/favourites", params={"tenant_name": first_tenant.name})

    assert [product["id"] for product in response.json()] == [first_product["id"]]


def test_favourites_brand_filter_404s_for_unknown_brand(client, as_user):
    response = client.get("/favourites", params={"tenant_name": "unknown-brand"})

    assert response.status_code == 404
