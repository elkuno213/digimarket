# DigiMarket API

DigiMarket is an API-only Flask e-commerce project. It implements configuration, JWT
authentication, public catalogue browsing, administrator product management, and client order
management. The HTTP contract is in [API.md](docs/API.md); this guide starts with an empty database
and exercises the complete required flow.

## Start locally

Run these commands from this directory. You need Python 3.11+.

Create `.env` and fill in its values:

```dotenv
DATABASE_PATH=<tmp-database-file-path>
JWT_SECRET_KEY=<replace-with-a-long-random-secret>
ADMIN_EMAIL=<admin@example.com>
ADMIN_NAME=<admin-name>
ADMIN_PASSWORD=<replace-with-an-8-character-minimum-password>
```

Then copy the empty database to the writable location named in `.env`:

```bash
cp digimarket.db <tmp-database-file-path>
```

Choose one dependency setup, then create the first administrator and start Flask.

### Using uv

```bash
uv sync

uv run flask onboard
uv run flask run --debug
```

### Using requirements.txt

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt

flask onboard
flask run --debug
```

Expected before the server starts:

```text
Administrator onboarded: <your-email>
```

Flask reads `.env` automatically. `flask onboard` is a trusted local, explicit setup command: it never runs when Flask starts. It
accepts required `--email`, `--name`, and `--password` values; this guide supplies them through the
`ADMIN_EMAIL`, `ADMIN_NAME`, and `ADMIN_PASSWORD` environment-variable defaults. It hashes the
password, creates the first administrator only, and refuses once an administrator exists. In
contrast, public `POST /api/auth/register` always creates a `client`; it cannot create an
administrator.

## Demo

Use a new `.env` and database copy for this walkthrough. The fresh database gives the first product
ID `1`, the second product ID `2`, and orders IDs `1`, `2`, and `3`.

```dotenv
API_URL=http://127.0.0.1:5000
DATABASE_PATH=/tmp/demo.db
JWT_SECRET_KEY=local-demo-secret-change-before-deployment
ADMIN_EMAIL=admin@digimarket.test
ADMIN_NAME="Demo Admin"
ADMIN_PASSWORD=admin-demo-password
CLIENT_ONE_EMAIL=client.one@digimarket.test
CLIENT_ONE_NAME="Client One"
CLIENT_ONE_PASSWORD=client-one-password
CLIENT_TWO_EMAIL=client.two@digimarket.test
CLIENT_TWO_NAME="Client Two"
CLIENT_TWO_PASSWORD=client-two-password
```

Start the server in one terminal:

```bash
cp digimarket.db /tmp/demo.db            # Expected: a new empty demo database.
uv run flask onboard                     # Expected: Administrator onboarded: admin@digimarket.test
uv run flask run --debug                 # Expected: Running on http://127.0.0.1:5000
```

Run the following in a second terminal:

```bash
set -a; . ./.env; set +a                 # Expected: values from .env are available to curl.

# Expected: ADMIN_TOKEN contains an access token.
ADMIN_TOKEN="$(curl -sS -X POST "$API_URL/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"mot_de_passe\":\"$ADMIN_PASSWORD\"}" \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')"

# Expected: HTTP/1.1 201 CREATED and role "client".
curl -i -X POST "$API_URL/api/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$CLIENT_ONE_EMAIL\",\"nom\":\"$CLIENT_ONE_NAME\",\"mot_de_passe\":\"$CLIENT_ONE_PASSWORD\"}"
curl -i -X POST "$API_URL/api/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$CLIENT_TWO_EMAIL\",\"nom\":\"$CLIENT_TWO_NAME\",\"mot_de_passe\":\"$CLIENT_TWO_PASSWORD\"}"

# Expected: both variables contain an access token.
CLIENT_ONE_TOKEN="$(curl -sS -X POST "$API_URL/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$CLIENT_ONE_EMAIL\",\"mot_de_passe\":\"$CLIENT_ONE_PASSWORD\"}" \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')"
CLIENT_TWO_TOKEN="$(curl -sS -X POST "$API_URL/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$CLIENT_TWO_EMAIL\",\"mot_de_passe\":\"$CLIENT_TWO_PASSWORD\"}" \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')"

# Expected: HTTP/1.1 201 CREATED; first product has id 1 and stock 5.
curl -i -X POST "$API_URL/api/produits" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"nom":"Keyboard","description":"Demo product","categorie":"Accessories","prix":89.99,"quantite_stock":5}'

# Expected: HTTP/1.1 201 CREATED; second product has id 2.
curl -i -X POST "$API_URL/api/produits" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"nom":"Cable","description":"Temporary product","categorie":"Accessories","prix":9.99,"quantite_stock":3}'

# Expected: HTTP/1.1 200 OK; public catalogue and search results need no token.
curl -i "$API_URL/api/produits"
curl -i "$API_URL/api/produits?q=keyboard"

# Expected: HTTP/1.1 200 OK, then 200 OK, then 200 OK with Product deleted.
curl -i -X PUT "$API_URL/api/produits/2" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"nom":"Cable","description":"Updated product","categorie":"Accessories","prix":12.99,"quantite_stock":4}'
curl -i "$API_URL/api/produits/2"
curl -i -X DELETE "$API_URL/api/produits/2" -H "Authorization: Bearer $ADMIN_TOKEN"

# Expected: HTTP/1.1 201 CREATED; order 1 is en_attente.
curl -i -X POST "$API_URL/api/commandes" -H "Authorization: Bearer $CLIENT_ONE_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"adresse_livraison":"1 Main Street","lignes":[{"produit_id":1,"quantite":2}]}'

# Expected: HTTP/1.1 200 OK for the client list, order header, and saved lines.
curl -i "$API_URL/api/commandes" -H "Authorization: Bearer $CLIENT_ONE_TOKEN"
curl -i "$API_URL/api/commandes/1" -H "Authorization: Bearer $CLIENT_ONE_TOKEN"
curl -i "$API_URL/api/commandes/1/lignes" -H "Authorization: Bearer $CLIENT_ONE_TOKEN"

# Expected: HTTP/1.1 200 OK; order 1 becomes validée and product 1 stock becomes 3.
curl -i -X PATCH "$API_URL/api/commandes/1" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' -d '{"statut":"validée"}'
curl -i "$API_URL/api/produits/1"

# Expected: HTTP/1.1 200 OK; order 1 becomes expédiée and stock stays 3.
curl -i -X PATCH "$API_URL/api/commandes/1" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' -d '{"statut":"expédiée"}'

# Expected: HTTP/1.1 201 CREATED; order 2 is en_attente.
curl -i -X POST "$API_URL/api/commandes" -H "Authorization: Bearer $CLIENT_TWO_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"adresse_livraison":"2 Main Street","lignes":[{"produit_id":1,"quantite":1}]}'

# Expected: HTTP/1.1 200 OK twice; order 2 is annulée and stock returns to 3.
curl -i -X PATCH "$API_URL/api/commandes/2" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' -d '{"statut":"validée"}'
curl -i -X PATCH "$API_URL/api/commandes/2" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' -d '{"statut":"annulée"}'

# Expected: HTTP/1.1 201 CREATED, then 200 OK; pending cancellation does not change stock.
curl -i -X POST "$API_URL/api/commandes" -H "Authorization: Bearer $CLIENT_TWO_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"adresse_livraison":"2 Main Street","lignes":[{"produit_id":1,"quantite":1}]}'
curl -i -X PATCH "$API_URL/api/commandes/3" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' -d '{"statut":"annulée"}'

# Expected: HTTP/1.1 200 OK; administrators can list all three orders.
curl -i "$API_URL/api/commandes" -H "Authorization: Bearer $ADMIN_TOKEN"

# Expected: HTTP/1.1 409 CONFLICT; shipped order history protects product 1.
curl -i -X DELETE "$API_URL/api/produits/1" -H "Authorization: Bearer $ADMIN_TOKEN"

# Expected: every request returns HTTP/1.1 403 FORBIDDEN.
curl -i -X POST "$API_URL/api/produits" -H "Authorization: Bearer $CLIENT_ONE_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"nom":"Forbidden","description":"No admin role","categorie":"Demo","prix":1,"quantite_stock":1}'
curl -i -X PATCH "$API_URL/api/commandes/1" -H "Authorization: Bearer $CLIENT_ONE_TOKEN" \
  -H 'Content-Type: application/json' -d '{"statut":"annulée"}'
curl -i "$API_URL/api/commandes/1" -H "Authorization: Bearer $CLIENT_TWO_TOKEN"
```

## Verify the project

Run the full quality gate from this directory:

```bash
uv run pytest
uv run ruff format --check app tests
uv run ruff check app tests
uv run mypy app
uvx ty check app tests
```

## Documentation

- [HTTP API contract](docs/API.md)
- [Implementation design](docs/DESIGN.md)
- [Supplied project description](docs/DESCRIPTION.md)
- [Supplied data structures](docs/STRUCTURE-DES-DONNEES.md)
- [Supplied project progression](docs/PROGRESSION.md)
