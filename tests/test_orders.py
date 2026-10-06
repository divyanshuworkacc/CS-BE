from tests.helpers import add_product


def test_marketplace_checkout_creates_brand_orders_in_one_request(
    client, make_admin, make_regular_user, login_as
):
    admin, first_brand = make_admin()
    login_as(admin)
    second_brand = client.post("/tenants", json={"name": "studio"}).json()
    first_product = add_product(
        client, first_brand.name, quantity=10, price=20.0, name="Canvas tote"
    )
    second_product = add_product(
        client, second_brand["name"], quantity=8, price=35.0, name="Linen throw"
    )

    customer, _ = make_regular_user(tenant_name=first_brand.name)
    login_as(customer)
    response = client.post(
        "/orders",
        json={
            "address": "12 Market Street, Springfield",
            "order_items": [
                {"product_id": first_product["id"], "quantity": 2},
                {"product_id": second_product["id"], "quantity": 3},
            ]
        },
    )

    assert response.status_code == 200
    orders = response.json()
    assert len(orders) == 2
    assert {order["tenant_id"] for order in orders} == {
        first_brand.id,
        second_brand["id"],
    }
    assert {order["amount"] for order in orders} == {40.0, 105.0}
    assert {order["address"] for order in orders} == {
        "12 Market Street, Springfield"
    }
    assert sum(order["total_quantity"] for order in orders) == 5
    assert client.get(f"/{first_brand.name}/products").json()[0]["quantity"] == 8
    assert client.get(f"/{second_brand['name']}/products").json()[0]["quantity"] == 5
    assert len(client.get("/orders").json()) == 2


def test_marketplace_checkout_is_atomic_when_one_brand_is_out_of_stock(
    client, make_admin, make_regular_user, login_as
):
    admin, first_brand = make_admin()
    login_as(admin)
    second_brand = client.post("/tenants", json={"name": "studio"}).json()
    first_product = add_product(
        client, first_brand.name, quantity=10, price=20.0, name="Canvas tote"
    )
    second_product = add_product(
        client, second_brand["name"], quantity=2, price=35.0, name="Linen throw"
    )

    customer, _ = make_regular_user(tenant_name=first_brand.name)
    login_as(customer)
    response = client.post(
        "/orders",
        json={
            "address": "12 Market Street, Springfield",
            "order_items": [
                {"product_id": first_product["id"], "quantity": 2},
                {"product_id": second_product["id"], "quantity": 2},
            ]
        },
    )

    assert response.status_code == 400
    assert client.get(f"/{first_brand.name}/products").json()[0]["quantity"] == 10
    assert client.get(f"/{second_brand['name']}/products").json()[0]["quantity"] == 2
    assert client.get("/orders").json() == []


def test_order_reduces_stock_and_computes_total(
    client, make_admin, make_regular_user, login_as
):
    admin, tenant = make_admin()
    login_as(admin)
    product = add_product(client, tenant.name, quantity=10, price=50.0)

    user, _ = make_regular_user(tenant_name=tenant.name)
    login_as(user)

    resp = client.post(
        f"/{tenant.name}/orders",
        json={"address": "12 Market Street, Springfield", "order_items": [{"product_id": product["id"], "quantity": 3}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_quantity"] == 3
    assert body["amount"] == 150.0
    assert body["address"] == "12 Market Street, Springfield"

    remaining = client.get(f"/{tenant.name}/products").json()[0]["quantity"]
    assert remaining == 7


def test_order_rejects_when_quantity_exceeds_stock(
    client, make_admin, make_regular_user, login_as
):
    admin, tenant = make_admin()
    login_as(admin)
    product = add_product(client, tenant.name, quantity=2)

    user, _ = make_regular_user(tenant_name=tenant.name)
    login_as(user)

    resp = client.post(
        f"/{tenant.name}/orders",
        json={"address": "12 Market Street, Springfield", "order_items": [{"product_id": product["id"], "quantity": 5}]},
    )
    assert resp.status_code == 400


def test_order_currently_rejects_buying_exact_remaining_stock(
    client, make_admin, make_regular_user, login_as
):
    """Documents CURRENT behavior: the check is `product.quantity > item.quantity`,
    so ordering exactly the remaining stock is rejected, not allowed. If you change
    that check to `>=`, flip this assertion to expect 200 instead."""
    admin, tenant = make_admin()
    login_as(admin)
    product = add_product(client, tenant.name, quantity=3)

    user, _ = make_regular_user(tenant_name=tenant.name)
    login_as(user)

    resp = client.post(
        f"/{tenant.name}/orders",
        json={"address": "12 Market Street, Springfield", "order_items": [{"product_id": product["id"], "quantity": 3}]},
    )
    assert resp.status_code == 400


def test_order_rejects_unknown_product(client, make_admin, login_as):
    admin, tenant = make_admin()
    login_as(admin)

    resp = client.post(
        f"/{tenant.name}/orders",
        json={"address": "12 Market Street, Springfield", "order_items": [{"product_id": 9999, "quantity": 1}]},
    )
    assert resp.status_code == 404


def test_get_orders_is_scoped_to_current_user(
    client, make_admin, make_regular_user, login_as
):
    admin, tenant = make_admin()
    login_as(admin)
    product = add_product(client, tenant.name, quantity=10)

    user_a, _ = make_regular_user(username="user_a", tenant_name=tenant.name)
    login_as(user_a)
    client.post(
        f"/{tenant.name}/orders",
        json={"address": "12 Market Street, Springfield", "order_items": [{"product_id": product["id"], "quantity": 1}]},
    )

    user_b, _ = make_regular_user(username="user_b", tenant_name=tenant.name)
    login_as(user_b)
    client.post(
        f"/{tenant.name}/orders",
        json={"address": "12 Market Street, Springfield", "order_items": [{"product_id": product["id"], "quantity": 2}]},
    )

    resp = client.get(f"/{tenant.name}/orders")
    orders = resp.json()
    assert len(orders) == 1
    assert orders[0]["total_quantity"] == 2  # only user_b's own order
