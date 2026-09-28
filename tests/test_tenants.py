from app import models


def test_admin_can_create_tenant(client, as_admin):
    resp = client.post("/tenants", json={"name": "nike"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "nike"


def test_non_admin_cannot_create_tenant(client, as_user):
    resp = client.post("/tenants", json={"name": "nike"})
    assert resp.status_code == 403


def test_tenant_list_is_public(client, db_session):
    db_session.add(models.Tenant(name="acme"))
    db_session.commit()

    resp = client.get("/tenants")
    assert resp.status_code == 200
    assert any(t["name"] == "acme" for t in resp.json())


def test_admin_can_delete_tenant(client, as_admin, db_session):
    temp = models.Tenant(name="temp-brand")
    db_session.add(temp)
    db_session.commit()

    resp = client.delete(f"/tenants/{temp.name}")
    assert resp.status_code == 200

    # deleting again should 404 — it's already gone
    resp = client.delete(f"/tenants/{temp.name}")
    assert resp.status_code == 404


def test_delete_unknown_tenant_404s(client, as_admin):
    resp = client.delete("/tenants/does-not-exist")
    assert resp.status_code == 404
