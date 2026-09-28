def test_current_profile_includes_local_role_and_tenant(client, as_user):
    user, tenant = as_user
    response = client.get("/users/me")
    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "name": user.name,
        "username": user.username,
        "tenant_id": None,
        "role_id": user.role_id,
        "role": "User",
        "tenant_name": None,
    }


def test_profile_requires_authentication(client):
    assert client.get("/users/me").status_code == 401


def test_admin_can_list_role_ids(client, as_admin):
    response = client.get("/roles")
    assert response.status_code == 200
    assert {role["name"] for role in response.json()} == {"Admin", "Tenant", "User"}


def test_other_users_cannot_list_roles(client, as_user):
    assert client.get("/roles").status_code == 403
