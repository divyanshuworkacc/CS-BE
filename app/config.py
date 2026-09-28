"""Keycloak settings. Passwords and service-account secrets come from the environment."""

import os

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "ecommerce")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "ecommerce-frontend")
ISSUER = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"
TOKEN_URL = f"{ISSUER}/protocol/openid-connect/token"
AUTHORIZATION_URL = f"{ISSUER}/protocol/openid-connect/auth"
JWKS_URL = f"{ISSUER}/protocol/openid-connect/certs"
