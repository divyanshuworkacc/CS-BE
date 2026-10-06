# E-commerce backend

FastAPI + SQLAlchemy + Keycloak. Python 3.12.

## The account model

All three roles use the same Keycloak login. The backend decides permissions
from its local role records; a login screen does not grant permissions.

| Role | Brand membership | Permissions |
| --- | --- | --- |
| Admin | None | Create/remove brands; create/manage brand logins; manage products |
| Tenant (brand manager) | One brand | Manage own brand's products; shop at any brand |
| User (customer) | None | Shop at any brand; own history and favourites |

Customers never choose a brand during signup. A manager uses the same account
for shopping, with no second registration. Brand URLs select the catalog or
management context, not a customer's membership. A manager can browse/buy from
another brand, but cannot enter its management dashboard or modify its products.

## Layout

```text
app/
  main.py          App startup and router registration
  config.py        Keycloak URLs and frontend client ID
  auth.py          Token verification and current account
  database.py      Database sessions and initialization
  models.py        Database tables
  schemas.py       Input validation and response shapes
  dependencies.py  Shared role/brand permission checks and pagination
  routers/         HTTP endpoints by feature
  services/
    accounts.py    Manager account creation and access revocation
    catalog.py     Shared, paginated product ordering
    keycloak.py    Keycloak account/password operations
scripts/seed_admin.py  Explicit platform-admin bootstrap
tests/             Isolated API and service tests
```

## Run and test

```bash
source fast-env/bin/activate
# Export the settings from .env.example with your actual values first.
python -m uvicorn app.main:app --reload --host localhost --port 9000
python -m pytest -q
```

The application does not automatically load `.env` files. For a fresh Python
environment install `requirements-dev.txt`. API docs: http://localhost:9000/docs.
The compatibility entry point `python main.py` also works.

`DATABASE_URL` optionally overrides the default local `ecommerce.db`. Startup
seeds the three roles and clears old brand assignments from Admin/User accounts.
Manager assignments, identities, products and purchase history are preserved.
Tests use a separate temporary database, never your application database.

## Keycloak setup needed

1. Start Keycloak at `http://localhost:8080` and use realm `ecommerce`. The backend
   launcher and frontend local settings use this same issuer. Use `localhost`
   consistently in the browser; Keycloak treats `127.0.0.1` as a different
   redirect origin.
2. Enable customer self-registration in the realm's Login settings. Configure
   public OIDC client `ecommerce-frontend`, Standard Flow enabled, PKCE S256,
   client authentication disabled, allowed redirect `http://localhost:5173/*`
   and web origin `http://localhost:5173`. Add the backend `/docs` redirect if
   using Swagger authentication. Do not put backend secrets in this public client.
3. Create a separate OIDC client `ecommerce-backend` with client authentication
   and service accounts enabled. Assign its service account the realm-management
   `manage-users` and `query-users` roles. Disable unnecessary interactive flows.
   Copy its Credentials secret into the backend-only exported environment variable
   `KEYCLOAK_ADMIN_CLIENT_SECRET`. Restart the backend after changing settings.
   This enables the admin to create/reset brand-manager credentials through the API.
4. Create your platform administrator's login in Keycloak, then grant that same
   username the local platform role explicitly:

   ```bash
   python -m scripts.seed_admin your_admin_username
   ```

   This does not create a Keycloak identity and does not create a fake platform brand.
   Keycloak server-administrator permissions and application Admin permissions are separate.
5. For username/password-only manager logins, review realm User Profile required
   attributes: this API provides username and first name, not email/last name.
   If those are required, Keycloak may request profile completion at first login.

The adapter follows the official [Keycloak Admin REST API](https://www.keycloak.org/docs-api/latest/rest-api/index.html).
Use HTTPS outside local development. Never commit or put the service secret in
frontend environment variables. Missing provisioning configuration returns 503
and does not create a local manager account. Tests mock Keycloak; they do not
replace a live realm integration test. If a network timeout leaves an account
creation uncertain, check Keycloak before retrying the username.

## API flow

All private calls need `Authorization: Bearer <Keycloak access token>`.

- Customer: register/login in Keycloak, then `POST /users` with
  `{"name":"Alice"}` once to create the application profile. Username comes
  from the token. Sending `tenant_id`, `role_id` or a password is rejected.
- Admin: `POST /tenants` with `{"name":"nike"}`.
- Admin: `POST /nike/users` with
  `{"name":"Nike Manager","username":"nike_manager","password":"a-strong-password"}`.
  This creates the real Keycloak login and assigns the local Tenant role to Nike.
  Passwords are never saved in the application database or returned in responses.
- Manager: login using those credentials; `GET /nike/dashboard` checks management
  access. Product POST/PATCH/DELETE under `/nike/products` uses that same check.
  `/adidas/dashboard` is forbidden to Nike's manager.
- Everyone: `GET /tenants`, `GET /categories` for categories across all brands, or
  `GET /categories?tenant_name=nike` for one brand. Category lists are distinct and
  unpaginated. Product browsing uses `GET /nike/products?search=shoe&category=footwear&sort=price-high`.
  Catalogs also accept `sort=featured` (default), `price-low`, `price-high`, or
  `name`; sorting is applied in the database before `skip`/`limit` pagination.
- Signed-in shopper or manager: `POST /orders` with
  `{"address":"12 Market Street, Springfield","order_items":[{"product_id":1,"quantity":2},{"product_id":8,"quantity":1}]}`
  where `address` is the delivery destination, for a single marketplace checkout across brands. The backend validates every
  item and commits one brand-scoped order per brand atomically. Use
  `POST /nike/orders` when placing an order for only one brand.
- Own history: `GET /orders` across brands, or `GET /nike/orders` for one brand.
- Own favourites: `GET /favourites?sort=name`; `POST /favourites/{product_id}` toggles.
- Profile: `GET /users/me`; customer/admin `tenant_id` and `tenant_name` are null.
- Admin manager maintenance: `GET /nike/users`,
  `PATCH /nike/users/nike_manager` with name and/or password,
  `DELETE /nike/users/nike_manager` to revoke brand access while keeping the
  account as a regular customer and preserving its purchase history.

Lists accept `skip` (minimum 0) and `limit` (1–100, default 10).
Orders retain the assignment's strict rule: quantity must be **less than** stock.
Products/brands with order history cannot be hard-deleted (409); set a product's
quantity to zero to stop new purchases. Deleting a brand without orders removes
its products/favourites and makes its managers regular customers.

## Frontend compatibility

The frontend uses a brand filter for product browsing and one bag across brands.
Its checkout sends the bag to `POST /orders`, which creates the appropriate
brand-scoped order records in one transaction. The API enforces authorization
independently of frontend visibility.
