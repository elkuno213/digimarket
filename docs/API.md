# DigiMarket HTTP API

Base URL: `/api`. Requests and responses are JSON. Send `Authorization: Bearer <access_token>` for
protected routes. Times are ISO 8601 UTC. Successful `GET`/`PUT`/`PATCH` responses are `200` unless
shown otherwise. See the [README](../README.md) for local startup and the complete walkthrough.

## Conventions and errors

All endpoint and framework failures use `{"error":"..."}`: bad input `400`, missing/invalid token
`401`, forbidden role or ownership `403`, absent resource `404`, and stock or state conflict `409`.
Framework `404`/`405` are JSON; unexpected failures return a non-leaking JSON `500`.

## Authentication

| Route | Request | Success | Errors |
| --- | --- | --- | --- |
| `POST /api/auth/register` | `email`, `nom`, `mot_de_passe` | `201` user `{id,email,nom,role,date_creation}` | `400`, `409` |
| `POST /api/auth/login` | `email`, `mot_de_passe` | `{access_token}` | `400`, `401` |

Registration trims and normalizes email, requires a nonblank name and an eight-character password,
and always creates a `client` (a supplied role cannot elevate access). Login returns the same `401`
for unknown email and wrong password.

## Products

A product is `{id,nom,description,categorie,prix,quantite_stock,date_creation}`. Public reads return
that representation (a list for the catalogue). Product writes require all editable fields:
`nom`, `description`, and `categorie` are nonblank; `prix` is positive; `quantite_stock` is a
nonnegative integer. `date_creation` is server generated.

| Route | Access | Request / response | Errors |
| --- | --- | --- | --- |
| `GET /api/produits` | Public | List; optional `q` is a literal, case-insensitive partial match on name, description, category. | — |
| `GET /api/produits/{id}` | Public | One product. | `404` |
| `POST /api/produits` | Admin | Complete product; `201` product. | `400`, `401`, `403` |
| `PUT /api/produits/{id}` | Admin | Complete replacement; product. | `400`, `401`, `403`, `404` |
| `DELETE /api/produits/{id}` | Admin | `{message:"Product deleted."}` | `401`, `403`, `404`, `409` |

Deletion preserves non-pending history: a reference in a `validée`, `expédiée`, `annulée`, null, or
unknown-status order returns `409` unchanged. If references are only `en_attente`, it atomically
removes each entire pending order and its lines (including other products), then the product. Stock
does not change; later reads of those orders return `404`.

## Orders

Every order route requires authentication. An order header is
`{id,utilisateur_id,date_commande,adresse_livraison,statut}`; a line is
`{id,produit_id,quantite,prix_unitaire}`. `prix_unitaire` is the price snapshot at creation.

| Route | Access | Request / response | Errors |
| --- | --- | --- | --- |
| `GET /api/commandes` | User | Own headers; admins receive all headers. | `401` |
| `GET /api/commandes/{id}` | Owner/admin | One header. | `401`, `403`, `404` |
| `POST /api/commandes` | User | Exactly `adresse_livraison` and nonempty `lignes`; `201` pending header. Each line is exactly positive-integer `produit_id`, `quantite`, with no duplicate product. | `400`, `401`, `404`, `409` |
| `PATCH /api/commandes/{id}` | Admin | Exactly `{statut}`; updated header. | `400`, `401`, `403`, `404`, `409` |
| `GET /api/commandes/{id}/lignes` | Owner/admin | Saved line list. | `401`, `403`, `404` |

Creation checks stock but neither reserves nor deducts it. There is no cross-session stock locking.

| Current status | Allowed target | Stock effect |
| --- | --- | --- |
| `en_attente` | `validée` | Deduct every line only after all lines pass stock checks. |
| `en_attente` | `annulée` | No change. |
| `validée` | `expédiée` | No change. |
| `validée` | `annulée` | Restore every deducted line. |
| `expédiée`, `annulée` | None | Terminal. |

An invalid transition or insufficient stock returns `409`; the stock-changing operations are
transactional, so failed validation leaves status and stock unchanged.
