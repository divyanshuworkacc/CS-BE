from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.config import KEYCLOAK_CLIENT_ID

from app.database import init_db
from app.routers import favourites, orders, products, tenants, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


tags_metadata = [
    {"name": "Tenants", "description": "Admin-managed brand records."},
    {
        "name": "Users",
        "description": "Independent customer signup and admin-managed brand logins.",
    },
    {
        "name": "Products",
        "description": "Per-tenant product catalog, search, and filtering.",
    },
    {"name": "Orders", "description": "Placing orders and viewing order history."},
    {"name": "Favourites", "description": "Mark, unmark, and list favourite products."},
]

app = FastAPI(
    lifespan=lifespan,
    openapi_tags=tags_metadata,
    swagger_ui_init_oauth={
        "clientId": KEYCLOAK_CLIENT_ID,
        "usePkceWithAuthorizationCodeGrant": True,
    },
)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Never echo submitted passwords in validation errors.
    errors = [
        {key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


for router in (
    tenants.router,
    users.router,
    products.router,
    orders.router,
    favourites.router,
):
    app.include_router(router)
