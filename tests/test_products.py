from app import models
from tests.helpers import add_product


def test_admin_can_add_product_to_any_tenant(client, as_admin):
    _, tenant = as_admin
    product = add_product(client, tenant.name, name="Air Max")
    assert product["tenant_id"] == tenant.id


def test_tenant_can_add_product_to_own_tenant(client, as_tenant):
    _, tenant = as_tenant
    resp = client.post(
        f"/{tenant.name}/products",
        json={"name": "Hoodie", "category": "apparel", "quantity": 5, "price": 60.0},
    )
    assert resp.status_code == 200


def test_tenant_cannot_add_product_to_other_tenant(client, as_tenant, db_session):
    other = models.Tenant(name="other-brand")
    db_session.add(other)
    db_session.commit()

    resp = client.post(
        f"/{other.name}/products",
        json={"name": "Hoodie", "category": "apparel", "quantity": 5, "price": 60.0},
    )
    assert resp.status_code == 403


def test_regular_user_cannot_add_product(client, as_user):
    _, tenant = as_user
    resp = client.post(
        f"/{tenant.name}/products",
        json={"name": "Hoodie", "category": "apparel", "quantity": 5, "price": 60.0},
    )
    assert resp.status_code == 403


def test_search_filters_by_name_substring(client, as_admin):
    _, tenant = as_admin
    add_product(client, tenant.name, name="Air Max 90")
    add_product(client, tenant.name, name="Classic Tee")

    resp = client.get(f"/{tenant.name}/products", params={"search": "Air"})
    names = [p["name"] for p in resp.json()]
    assert names == ["Air Max 90"]


def test_category_filter(client, as_admin):
    _, tenant = as_admin
    add_product(client, tenant.name, name="Air Max 90")
    resp1 = client.post(
        f"/{tenant.name}/products",
        json={"name": "Classic Tee", "category": "apparel", "quantity": 5, "price": 20},
    )
    assert resp1.status_code == 200

    resp = client.get(f"/{tenant.name}/products", params={"category": "apparel"})
    names = [p["name"] for p in resp.json()]
    assert names == ["Classic Tee"]


def test_rename_rejects_duplicate_name_within_tenant(client, as_admin):
    _, tenant = as_admin
    add_product(client, tenant.name, name="Air Max 90")
    p2 = add_product(client, tenant.name, name="Classic Tee")

    resp = client.patch(
        f"/{tenant.name}/products/{p2['id']}", json={"name": "Air Max 90"}
    )
    assert resp.status_code == 400


def test_delete_product(client, as_admin):
    _, tenant = as_admin
    product = add_product(client, tenant.name)

    resp = client.delete(f"/{tenant.name}/products/{product['id']}")
    assert resp.status_code == 200

    resp = client.get(f"/{tenant.name}/products")
    assert all(p["id"] != product["id"] for p in resp.json())
