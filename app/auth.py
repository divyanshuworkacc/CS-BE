"""All three account types use Keycloak. The database decides application permissions."""

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2AuthorizationCodeBearer
from jwt import PyJWKClient
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app import models
from app.config import AUTHORIZATION_URL, ISSUER, JWKS_URL, TOKEN_URL
from app.database import get_db

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=AUTHORIZATION_URL,
    tokenUrl=TOKEN_URL,
)
jwks_client = PyJWKClient(JWKS_URL)


def get_token_payload(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=ISSUER,
            options={"verify_aud": False, "require": ["exp", "sub"]},
        )
    except jwt.PyJWKClientConnectionError:
        raise HTTPException(
            status_code=503, detail="Cannot reach the login service"
        ) from None
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def get_current_user(
    payload: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
) -> models.User:
        username = payload.get("preferred_username")
        if not isinstance(username, str) or not username.strip():
            raise HTTPException(status_code=401, detail="Token missing preferred_username")
        username = username.strip().lower()

        user = (
            db.query(models.User)
            .filter(func.lower(models.User.username) == username)
            .first()
        )

        if user is None:
            token_name = payload.get("name")
            if not isinstance(token_name, str) or not token_name.strip():
                given_name = payload.get("given_name", "")
                family_name = payload.get("family_name", "")
                token_name = f"{given_name} {family_name}".strip()
            name = token_name or username

            role = db.query(models.Role).filter(models.Role.name == "User").one()
            user = models.User(
                name=name,
                username=username,
                role_id=role.id,
                tenant_id=None,
            )
            db.add(user)

            try:
                db.commit()
            except IntegrityError:
                # Another simultaneous request may have created this user first.
                db.rollback()
                user = (
                    db.query(models.User)
                    .filter(func.lower(models.User.username) == username)
                    .first()
                )
                if user is None:
                    raise
            else:
                db.refresh(user)

        return user
