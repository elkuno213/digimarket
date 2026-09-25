# DigiMarket HTTP API

## Overview

- Base URL: `/api`.
- Requests and responses use JSON.
- Protected routes need `Authorization: Bearer <access_token>`.
- Dates use ISO 8601 UTC.
- Successful `GET`, `PUT`, and `PATCH` responses return `200` unless a table says otherwise.
- See the [README](../README.md) for local startup and the complete walkthrough.

## Conventions and errors

- All errors use `{"error":"..."}`.
- `400`: invalid input.
- `401`: missing or invalid token.
- `403`: role or ownership is not allowed.
- `404`: resource does not exist.
- `409`: stock or order state conflict.
- Flask `404` and `405` errors also use JSON. Unexpected failures return a safe JSON `500`.

## Authentication

| Route | Request | Success | Errors |
| --- | --- | --- | --- |
| `POST /api/auth/register` | `email`, `nom`, `mot_de_passe` | `201` user `{id,email,nom,role,date_creation}` | `400`, `409` |
| `POST /api/auth/login` | `email`, `mot_de_passe` | `{access_token}` | `400`, `401` |

- Registration trims and normalizes email.
- A name is required. Password must contain at least eight characters.
- Registration always creates a `client`; a request cannot assign `admin`.
- Login uses the same `401` response for an unknown email and a wrong password.

## Products

- A product is `{id,nom,description,categorie,prix,quantite_stock,date_creation}`.
- Public reads return one product or a catalogue list.
- Product writes need every editable field.
- `nom`, `description`, and `categorie` must contain text.
- `prix` must be positive. `quantite_stock` must be a nonnegative integer.
- Server creates `date_creation`.

| Route | Access | Request / response | Errors |
| --- | --- | --- | --- |
| `GET /api/produits` | Public | List; optional `q` is a literal, case-insensitive partial match on name, description, category. | — |
| `GET /api/produits/{id}` | Public | One product. | `404` |
| `POST /api/produits` | Admin | Complete product; `201` product. | `400`, `401`, `403` |
| `PUT /api/produits/{id}` | Admin | Complete replacement; product. | `400`, `401`, `403`, `404` |
| `DELETE /api/produits/{id}` | Admin | `{message:"Product deleted."}` | `401`, `403`, `404`, `409` |

- A product in a non-pending order stays as history. Deletion returns `409`.
- A product used only by `en_attente` orders can be deleted.
- Deletion removes each affected pending order and all of its lines, then removes the product.
- Stock does not change. Later reads of removed orders return `404`.

## Orders

- Every order route needs authentication.
- An order header is `{id,utilisateur_id,date_commande,adresse_livraison,statut}`.
- A line is `{id,produit_id,quantite,prix_unitaire}`.
- `prix_unitaire` is saved when the order is created.

| Route | Access | Request / response | Errors |
| --- | --- | --- | --- |
| `GET /api/commandes` | User | Own headers; admins receive all headers. | `401` |
| `GET /api/commandes/{id}` | Owner/admin | One header. | `401`, `403`, `404` |
| `POST /api/commandes` | User | Exactly `adresse_livraison` and nonempty `lignes`; `201` pending header. Each line is exactly positive-integer `produit_id`, `quantite`, with no duplicate product. | `400`, `401`, `404`, `409` |
| `PATCH /api/commandes/{id}` | Admin | Exactly `{statut}`; updated header. | `400`, `401`, `403`, `404`, `409` |
| `GET /api/commandes/{id}/lignes` | Owner/admin | Saved line list. | `401`, `403`, `404` |

- Creation checks stock but does not reserve or deduct it.
- There is no stock lock between sessions.

| Current status | Allowed target | Stock effect |
| --- | --- | --- |
| `en_attente` | `validée` | Deduct every line only after all lines pass stock checks. |
| `en_attente` | `annulée` | No change. |
| `validée` | `expédiée` | No change. |
| `validée` | `annulée` | Restore every deducted line. |
| `expédiée`, `annulée` | None | Terminal. |

- Invalid state changes and insufficient stock return `409`.
- A failed stock change leaves status and stock unchanged.
