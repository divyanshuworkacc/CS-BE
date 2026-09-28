"""Create/reset brand logins in Keycloak"""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException

from app.config import KEYCLOAK_REALM, KEYCLOAK_URL, TOKEN_URL


class KeycloakAdmin:
    def __init__(self):
        self.client_id = os.getenv("KEYCLOAK_ADMIN_CLIENT_ID", "ecommerce-backend")
        self.client_secret = os.getenv("KEYCLOAK_ADMIN_CLIENT_SECRET", "")
        self.base_url = f"{KEYCLOAK_URL}/admin/realms/{quote(KEYCLOAK_REALM, safe='')}"

    def _send(self, request: Request):
        try:
            with urlopen(request, timeout=10) as response:
                body = response.read()
                return (json.loads(body) if body else None), response.headers
        except HTTPError as error:
            if error.code == 409:
                raise HTTPException(
                    409, "Username already exists in Keycloak"
                ) from None
            if error.code == 400:
                raise HTTPException(
                    400, "Keycloak rejected the account details or password policy"
                ) from None
            if error.code in (401, 403):
                raise HTTPException(
                    503, "Keycloak account provisioning is not configured correctly"
                ) from None
            raise HTTPException(
                502, "Keycloak could not complete the account operation"
            ) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise HTTPException(
                503, "Keycloak account service is unavailable"
            ) from None

    def _token(self) -> str:
        if not self.client_secret:
            raise HTTPException(
                503, "Set KEYCLOAK_ADMIN_CLIENT_SECRET to enable brand-login creation"
            )
        data = urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
        ).encode()
        body, _ = self._send(
            Request(
                TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        )
        if not isinstance(body, dict) or not body.get("access_token"):
            raise HTTPException(502, "Keycloak did not return a service token")
        return body["access_token"]

    def _request(self, method: str, path: str, body=None):
        return self._send(
            Request(
                self.base_url + path,
                method=method,
                data=json.dumps(body).encode() if body is not None else None,
                headers={
                    "Authorization": f"Bearer {self._token()}",
                    "Content-Type": "application/json",
                },
            )
        )

    def create_user(self, username: str, name: str, password: str) -> str:
        _, headers = self._request(
            "POST",
            "/users",
            {
                "username": username,
                "firstName": name,
                "enabled": True,
                "credentials": [
                    {"type": "password", "value": password, "temporary": False}
                ],
            },
        )
        location = headers.get("Location", "")
        if not location:
            raise HTTPException(
                502,
                "Keycloak created an account without returning its ID; check it before retrying",
            )
        return location.rstrip("/").rsplit("/", 1)[-1]

    def reset_password(self, username: str, password: str):
        users, _ = self._request(
            "GET", "/users?" + urlencode({"username": username, "exact": "true"})
        )
        if not users:
            raise HTTPException(404, "Brand login no longer exists in Keycloak")
        user_id = quote(users[0]["id"], safe="")
        self._request(
            "PUT",
            f"/users/{user_id}/reset-password",
            {
                "type": "password",
                "value": password,
                "temporary": False,
            },
        )

    def delete_created_user(self, user_id: str):
        """Compensate only for a new Keycloak account whose local save failed."""
        self._request("DELETE", f"/users/{quote(user_id, safe='')}")


def get_keycloak_admin() -> KeycloakAdmin:
    return KeycloakAdmin()
