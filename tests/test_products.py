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


def test_categories_are_unpaginated_and_can_be_scoped_to_tenant(
    client, as_admin, db_session
):
    _, tenant = as_admin
    for index in range(11):
        response = client.post(
            f"/{tenant.name}/products",
            json={
                "name": f"Product {index}",
                "category": f"category-{index:02}",
                "quantity": 1,
                "price": 1,
            },
        )
        assert response.status_code == 200

    other_tenant = models.Tenant(name="other-brand")
    db_session.add(other_tenant)
    db_session.commit()
    add_product(client, other_tenant.name, name="Other brand product")

    all_categories = client.get("/categories")
    tenant_categories = client.get("/categories", params={"tenant_name": tenant.name})

    assert all_categories.status_code == 200
    assert "category-10" in all_categories.json()
    assert "misc" in all_categories.json()
    assert tenant_categories.json() == [f"category-{index:02}" for index in range(11)]


def test_categories_return_404_for_unknown_tenant(client):
    response = client.get("/categories", params={"tenant_name": "unknown-brand"})

    assert response.status_code == 404


def test_sort_is_applied_across_brands_before_pagination(client, as_admin, db_session):
    _, tenant = as_admin
    add_product(client, tenant.name, name="Budget option", price=10)
    add_product(client, tenant.name, name="Middle option", price=100)
    other = models.Tenant(name="second-brand")
    db_session.add(other)
    db_session.commit()
    add_product(client, other.name, name="Premium option", price=1000)

    first_page = client.get("/products", params={"sort": "price-high", "limit": 1})
    second_page = client.get(
        "/products", params={"sort": "price-high", "skip": 1, "limit": 1}
    )

    assert [product["name"] for product in first_page.json()] == ["Premium option"]
    assert [product["name"] for product in second_page.json()] == ["Middle option"]


def test_name_sort_is_case_insensitive_for_brand_catalog(client, as_admin):
    _, tenant = as_admin
    add_product(client, tenant.name, name="zebra", price=10)
    add_product(client, tenant.name, name="Apple", price=100)

    response = client.get(f"/{tenant.name}/products", params={"sort": "name"})

    assert [product["name"] for product in response.json()] == ["Apple", "zebra"]


def test_product_sort_rejects_unknown_values(client):
    response = client.get("/products", params={"sort": "random"})

    assert response.status_code == 422


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
