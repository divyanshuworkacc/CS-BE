def add_product(client, tenant_name, quantity=10, price=50.0, name="Widget"):
    """Shared helper — assumes the caller is currently logged in as Admin or Tenant."""
    resp = client.post(
        f"/{tenant_name}/products",
        json={"name": name, "category": "misc", "quantity": quantity, "price": price},
    )
    return resp.json()
