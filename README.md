# DigiMarket API

DigiMarket is an API-only Flask e-commerce project. It implements configuration, JWT
authentication, public catalogue browsing, administrator product management, and client order
management. The HTTP contract is in [API.md](docs/API.md); this guide starts with an empty database
and exercises the complete required flow.

## Start a disposable local instance

Run these commands from `python/`. You need Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync

DEMO_DIR="$(mktemp -d)"
export DATABASE_PATH="$DEMO_DIR/digimarket.db"
read -r -s -p "JWT signing secret: " JWT_SECRET_KEY
printf '\n'
export JWT_SECRET_KEY

cp digimarket.db "$DATABASE_PATH"

read -r -p "Administrator email: " ADMIN_EMAIL
read -r -p "Administrator name: " ADMIN_NAME
read -r -s -p "Administrator password (8+ characters): " ADMIN_PASSWORD
printf '\n'
export ADMIN_EMAIL ADMIN_NAME ADMIN_PASSWORD

uv run flask onboard
uv run flask run --debug
```

Expected before the server starts:

```text
Administrator onboarded: <your-email>
```

`digimarket.db` is the sole tracked database and is an empty schema. The command copies it to a
temporary, writable location, so the project file remains unchanged. Stop Flask and delete
`$DEMO_DIR` when finished to discard every account, product, and order created below.

`flask onboard` is a trusted local, explicit setup command: it never runs when Flask starts. It
accepts required `--email`, `--name`, and `--password` values; this guide supplies them through the
`ADMIN_EMAIL`, `ADMIN_NAME`, and `ADMIN_PASSWORD` environment-variable defaults. It hashes the
password, creates the first administrator only, and refuses once an administrator exists. In
contrast, public `POST /api/auth/register` always creates a `client`; it cannot create an
administrator.

## Complete demo walkthrough

Keep Flask running in the first terminal. Open a second terminal in `python/`, then re-enter the
administrator email and password you chose above; terminals do not share exported variables. These
commands use only `curl` and `uv run python`, so `jq` is unnecessary.

### 1. Authenticate the administrator and create two clients

```bash
export API_URL="http://127.0.0.1:5000"
read -r -p "Administrator email (from terminal 1): " ADMIN_EMAIL
read -r -s -p "Administrator password (from terminal 1): " ADMIN_PASSWORD
printf '\n'
read -r -s -p "Client One password (8+ characters): " CLIENT_ONE_PASSWORD
printf '\n'
read -r -s -p "Client Two password (8+ characters): " CLIENT_TWO_PASSWORD
printf '\n'

json_field() {
  uv run python -c 'import json, sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"
}
json_object() {
  uv run python -c 'import json, sys; print(json.dumps(dict(zip(sys.argv[1::2], sys.argv[2::2]))))' "$@"
}

request() {
  RESPONSE=$(curl -sS --write-out $'\n%{http_code}' "$@")
  HTTP_CODE=${RESPONSE##*$'\n'}
  RESPONSE_BODY=${RESPONSE%$'\n'*}
}
show() {
  curl -sS --write-out '\nHTTP %{http_code}\n' "$@"
}

request --request POST "$API_URL/api/auth/login" \
  --header 'Content-Type: application/json' \
  --data "$(json_object email "$ADMIN_EMAIL" mot_de_passe "$ADMIN_PASSWORD")"
ADMIN_LOGIN=$RESPONSE_BODY
ADMIN_TOKEN=$(printf '%s' "$ADMIN_LOGIN" | json_field access_token)
printf 'Administrator login: HTTP %s; token received\n' "$HTTP_CODE"

request --request POST "$API_URL/api/auth/register" \
  --header 'Content-Type: application/json' \
  --data "$(json_object email client.one@example.test nom 'Client One' mot_de_passe "$CLIENT_ONE_PASSWORD")"
CLIENT_ONE_REGISTER=$RESPONSE_BODY
printf 'Client One register: HTTP %s; id=%s email=%s role=%s\n' "$HTTP_CODE" \
  "$(printf '%s' "$CLIENT_ONE_REGISTER" | json_field id)" \
  "$(printf '%s' "$CLIENT_ONE_REGISTER" | json_field email)" \
  "$(printf '%s' "$CLIENT_ONE_REGISTER" | json_field role)"
request --request POST "$API_URL/api/auth/register" \
  --header 'Content-Type: application/json' \
  --data "$(json_object email client.two@example.test nom 'Client Two' mot_de_passe "$CLIENT_TWO_PASSWORD")"
CLIENT_TWO_REGISTER=$RESPONSE_BODY
printf 'Client Two register: HTTP %s; id=%s email=%s role=%s\n' "$HTTP_CODE" \
  "$(printf '%s' "$CLIENT_TWO_REGISTER" | json_field id)" \
  "$(printf '%s' "$CLIENT_TWO_REGISTER" | json_field email)" \
  "$(printf '%s' "$CLIENT_TWO_REGISTER" | json_field role)"

request --request POST "$API_URL/api/auth/login" \
  --header 'Content-Type: application/json' \
  --data "$(json_object email client.one@example.test mot_de_passe "$CLIENT_ONE_PASSWORD")"
CLIENT_ONE_LOGIN=$RESPONSE_BODY
CLIENT_ONE_TOKEN=$(printf '%s' "$CLIENT_ONE_LOGIN" | json_field access_token)
printf 'Client One login: HTTP %s; token received\n' "$HTTP_CODE"
request --request POST "$API_URL/api/auth/login" \
  --header 'Content-Type: application/json' \
  --data "$(json_object email client.two@example.test mot_de_passe "$CLIENT_TWO_PASSWORD")"
CLIENT_TWO_LOGIN=$RESPONSE_BODY
CLIENT_TWO_TOKEN=$(printf '%s' "$CLIENT_TWO_LOGIN" | json_field access_token)
printf 'Client Two login: HTTP %s; token received\n' "$HTTP_CODE"
```

Expected: each registration returns `201` with `role: "client"`; each login returns `200` with an
`access_token`. The onboarded account logs in with `role: "admin"`.

### 2. Create products, then browse the public catalogue

The administrator creates one unreferenced product for the full CRUD lifecycle and three products
for independent stock examples.

```bash
create_product() {
  request --request POST "$API_URL/api/produits" \
    --header "Authorization: Bearer $ADMIN_TOKEN" \
    --header 'Content-Type: application/json' \
    --data "$1"
}

create_product '{"nom":"Demo Cable","description":"Temporary USB-C cable","categorie":"Accessories","prix":9.5,"quantite_stock":12}'
MANAGED_PRODUCT=$RESPONSE_BODY
MANAGED_PRODUCT_ID=$(printf '%s' "$MANAGED_PRODUCT" | json_field id)
printf 'Managed product create: HTTP %s; id=%s name=%s stock=%s\n' "$HTTP_CODE" \
  "$MANAGED_PRODUCT_ID" "$(printf '%s' "$MANAGED_PRODUCT" | json_field nom)" \
  "$(printf '%s' "$MANAGED_PRODUCT" | json_field quantite_stock)"

create_product '{"nom":"Validation Widget","description":"For validation then shipping","categorie":"Demo","prix":10.0,"quantite_stock":5}'
VALIDATION_PRODUCT=$RESPONSE_BODY
VALIDATION_PRODUCT_ID=$(printf '%s' "$VALIDATION_PRODUCT" | json_field id)
printf 'Validation product create: HTTP %s; id=%s name=%s stock=%s\n' "$HTTP_CODE" \
  "$VALIDATION_PRODUCT_ID" "$(printf '%s' "$VALIDATION_PRODUCT" | json_field nom)" \
  "$(printf '%s' "$VALIDATION_PRODUCT" | json_field quantite_stock)"
create_product '{"nom":"Pending Cancel Widget","description":"For pending cancellation","categorie":"Demo","prix":11.0,"quantite_stock":7}'
PENDING_CANCEL_PRODUCT=$RESPONSE_BODY
PENDING_CANCEL_PRODUCT_ID=$(printf '%s' "$PENDING_CANCEL_PRODUCT" | json_field id)
printf 'Pending-cancel product create: HTTP %s; id=%s name=%s stock=%s\n' "$HTTP_CODE" \
  "$PENDING_CANCEL_PRODUCT_ID" "$(printf '%s' "$PENDING_CANCEL_PRODUCT" | json_field nom)" \
  "$(printf '%s' "$PENDING_CANCEL_PRODUCT" | json_field quantite_stock)"
create_product '{"nom":"Restore Widget","description":"For validated cancellation","categorie":"Demo","prix":12.0,"quantite_stock":6}'
RESTORE_PRODUCT=$RESPONSE_BODY
RESTORE_PRODUCT_ID=$(printf '%s' "$RESTORE_PRODUCT" | json_field id)
printf 'Restore product create: HTTP %s; id=%s name=%s stock=%s\n' "$HTTP_CODE" \
  "$RESTORE_PRODUCT_ID" "$(printf '%s' "$RESTORE_PRODUCT" | json_field nom)" \
  "$(printf '%s' "$RESTORE_PRODUCT" | json_field quantite_stock)"

show "$API_URL/api/produits"
show "$API_URL/api/produits?q=cable"
show "$API_URL/api/produits/$MANAGED_PRODUCT_ID"
```

Expected: every create returns `201` and an `id`; all three public reads return `200`. The search
returns the temporary cable without an access token.

### 3. Fully update and delete the unreferenced product

```bash
request --request PUT "$API_URL/api/produits/$MANAGED_PRODUCT_ID" \
  --header "Authorization: Bearer $ADMIN_TOKEN" \
  --header 'Content-Type: application/json' \
  --data '{"nom":"Updated Demo Cable","description":"Updated full replacement","categorie":"Demo","prix":14.5,"quantite_stock":9}'
UPDATED_PRODUCT=$RESPONSE_BODY
printf 'Managed product update: HTTP %s; id=%s name=%s stock=%s\n' "$HTTP_CODE" \
  "$(printf '%s' "$UPDATED_PRODUCT" | json_field id)" \
  "$(printf '%s' "$UPDATED_PRODUCT" | json_field nom)" \
  "$(printf '%s' "$UPDATED_PRODUCT" | json_field quantite_stock)"
show "$API_URL/api/produits/$MANAGED_PRODUCT_ID"
request --request DELETE "$API_URL/api/produits/$MANAGED_PRODUCT_ID" \
  --header "Authorization: Bearer $ADMIN_TOKEN"
printf 'Managed product delete: HTTP %s; message=%s\n' "$HTTP_CODE" \
  "$(printf '%s' "$RESPONSE_BODY" | json_field message)"
```

Expected: the `PUT` and public read return `200` with the updated fields. The delete returns `200`
with `{"message":"Product deleted."}`. This product has never appeared in an order, so deletion
does not affect order history.

### 4. Create and inspect client orders

Client One creates an order, then reads only their own list, header, and saved lines. Client Two
creates a different order for the ownership check and pending-cancellation example.

```bash
request --request POST "$API_URL/api/commandes" \
  --header "Authorization: Bearer $CLIENT_ONE_TOKEN" \
  --header 'Content-Type: application/json' \
  --data "{\"adresse_livraison\":\"1 Client One Street\",\"lignes\":[{\"produit_id\":$VALIDATION_PRODUCT_ID,\"quantite\":2}]}"
VALIDATION_ORDER=$RESPONSE_BODY
VALIDATION_ORDER_ID=$(printf '%s' "$VALIDATION_ORDER" | json_field id)
printf 'Validation order create: HTTP %s; id=%s status=%s\n' "$HTTP_CODE" \
  "$VALIDATION_ORDER_ID" "$(printf '%s' "$VALIDATION_ORDER" | json_field statut)"

request --request POST "$API_URL/api/commandes" \
  --header "Authorization: Bearer $CLIENT_TWO_TOKEN" \
  --header 'Content-Type: application/json' \
  --data "{\"adresse_livraison\":\"2 Client Two Street\",\"lignes\":[{\"produit_id\":$PENDING_CANCEL_PRODUCT_ID,\"quantite\":3}]}"
PENDING_CANCEL_ORDER=$RESPONSE_BODY
PENDING_CANCEL_ORDER_ID=$(printf '%s' "$PENDING_CANCEL_ORDER" | json_field id)
printf 'Pending-cancel order create: HTTP %s; id=%s status=%s\n' "$HTTP_CODE" \
  "$PENDING_CANCEL_ORDER_ID" "$(printf '%s' "$PENDING_CANCEL_ORDER" | json_field statut)"

request --request POST "$API_URL/api/commandes" \
  --header "Authorization: Bearer $CLIENT_ONE_TOKEN" \
  --header 'Content-Type: application/json' \
  --data "{\"adresse_livraison\":\"1 Client One Street\",\"lignes\":[{\"produit_id\":$RESTORE_PRODUCT_ID,\"quantite\":2}]}"
RESTORE_ORDER=$RESPONSE_BODY
RESTORE_ORDER_ID=$(printf '%s' "$RESTORE_ORDER" | json_field id)
printf 'Restore order create: HTTP %s; id=%s status=%s\n' "$HTTP_CODE" \
  "$RESTORE_ORDER_ID" "$(printf '%s' "$RESTORE_ORDER" | json_field statut)"

show "$API_URL/api/commandes" \
  --header "Authorization: Bearer $CLIENT_ONE_TOKEN"
show "$API_URL/api/commandes/$VALIDATION_ORDER_ID" \
  --header "Authorization: Bearer $CLIENT_ONE_TOKEN"
show "$API_URL/api/commandes/$VALIDATION_ORDER_ID/lignes" \
  --header "Authorization: Bearer $CLIENT_ONE_TOKEN"
```

Expected: each creation returns `201` with `statut: "en_attente"`. Client One's reads return `200`
and expose its two order headers, delivery address, and the saved line with `prix_unitaire`.

### 5. Demonstrate every order-state and stock rule

`stock` reads the public product detail. `set_status` returns the updated `statut` from an
administrator-only `PATCH`.

```bash
show_stock() {
  request "$API_URL/api/produits/$1"
  printf '%s: HTTP %s; stock=%s\n' "$2" "$HTTP_CODE" \
    "$(printf '%s' "$RESPONSE_BODY" | json_field quantite_stock)"
}
set_status() {
  request --request PATCH "$API_URL/api/commandes/$1" \
    --header "Authorization: Bearer $ADMIN_TOKEN" \
    --header 'Content-Type: application/json' \
    --data "{\"statut\":\"$2\"}"
  printf 'Order %s update: HTTP %s; status=%s\n' "$1" "$HTTP_CODE" \
    "$(printf '%s' "$RESPONSE_BODY" | json_field statut)"
}

show_stock "$VALIDATION_PRODUCT_ID" 'Validation product before'
set_status "$VALIDATION_ORDER_ID" 'validée'
show_stock "$VALIDATION_PRODUCT_ID" 'Validation product after validation'
set_status "$VALIDATION_ORDER_ID" 'expédiée'
show_stock "$VALIDATION_PRODUCT_ID" 'Validation product after shipping'

show_stock "$PENDING_CANCEL_PRODUCT_ID" 'Pending-cancel product before'
set_status "$PENDING_CANCEL_ORDER_ID" 'annulée'
show_stock "$PENDING_CANCEL_PRODUCT_ID" 'Pending-cancel product after cancellation'

show_stock "$RESTORE_PRODUCT_ID" 'Restore product before'
set_status "$RESTORE_ORDER_ID" 'validée'
show_stock "$RESTORE_PRODUCT_ID" 'Restore product after validation'
set_status "$RESTORE_ORDER_ID" 'annulée'
show_stock "$RESTORE_PRODUCT_ID" 'Restore product after cancellation'

show "$API_URL/api/commandes" \
  --header "Authorization: Bearer $ADMIN_TOKEN"
```

Expected: all `PATCH` requests return `200`. The printed stock values are `5 → 3 → 3` for
`en_attente → validée → expédiée`, `7 → 7` for `en_attente → annulée`, and `6 → 4 → 6` for
`en_attente → validée → annulée`. The final administrator list returns `200` and includes every
client's orders.

### 6. Check the access boundaries

```bash
curl -sS --output /dev/null --write-out 'Client product creation: HTTP %{http_code}\n' \
  --request POST "$API_URL/api/produits" \
  --header "Authorization: Bearer $CLIENT_ONE_TOKEN" \
  --header 'Content-Type: application/json' \
  --data '{"nom":"Forbidden","description":"No admin role","categorie":"Demo","prix":1.0,"quantite_stock":1}'
curl -sS --output /dev/null --write-out 'Client status update: HTTP %{http_code}\n' \
  --request PATCH "$API_URL/api/commandes/$VALIDATION_ORDER_ID" \
  --header "Authorization: Bearer $CLIENT_ONE_TOKEN" \
  --header 'Content-Type: application/json' \
  --data '{"statut":"annulée"}'
curl -sS --output /dev/null --write-out 'Other client order: HTTP %{http_code}\n' \
  "$API_URL/api/commandes/$PENDING_CANCEL_ORDER_ID" \
  --header "Authorization: Bearer $CLIENT_ONE_TOKEN"
```

Expected: all three commands print `HTTP 403`. Client accounts cannot manage products or order
statuses, and cannot read another client's order.

### 7. Final check

The walkthrough began with a copied empty schema, created the first trusted administrator locally,
registered clients through the public API, exercised public catalogue reads and full administrator
product CRUD, and demonstrated client ownership plus all required order-state stock effects. The
original tracked `digimarket.db` has not changed.

## Verify the project

Run the full quality gate from `python/`:

```bash
uv run pytest
uv run ruff format --check app tests
uv run ruff check app tests
uv run mypy app
uvx ty check app tests
```

## Documentation

- [HTTP API contract](docs/API.md)
- [Roadmap and implementation design](docs/DESIGN.md)
- [Supplied project description](docs/DESCRIPTION.md)
- [Supplied data structures](docs/STRUCTURE-DES-DONNEES.md)
- [Supplied milestone progression](docs/PROGRESSION.md)
