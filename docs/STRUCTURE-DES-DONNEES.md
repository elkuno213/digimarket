# Structure des données

Ce document détaille la structure de données à utiliser dans le cadre du projet Blent.ai sur le développement d’une API REST avec Flask E-commerce.

## Tables de données

L’application s’appuie sur quatre entités principales :

1. Utilisateurs : Stocke les informations de compte client et administrateur
2. Produits : Contient les informations du catalogue et des stocks
3. Commandes : Enregistre les informations générales des commandes passées
4. Lignes de commande : Détaille le contenu précis de chaque commande

## Utilisateur

| Champ | Type | Description |
| --- | --- | --- |
| id | Integer | Clé primaire |
| email | String | Email unique de l’utilisateur |
| password_hash | String | Mot de passe haché stocké |
| nom | String | Nom de l’utilisateur |
| role | String | Rôle: `client` ou `admin` |
| date_creation | DateTime | Date de création du compte |

L’API reçoit `mot_de_passe` en entrée et le hache avant de stocker le résultat dans `password_hash`.

## Produit

| Champ | Type | Description |
| --- | --- | --- |
| id | Integer | Clé primaire |
| nom | String | Nom du produit |
| description | Text | Description détaillée |
| categorie | String | Nom de la catégorie |
| prix | Float | Prix unitaire |
| quantite_stock | Integer | Quantité disponible en stock |
| date_creation | DateTime | Date d’ajout du produit |

## Commande

| Champ | Type | Description |
| --- | --- | --- |
| id | Integer | Clé primaire |
| utilisateur_id | Integer | Clé étrangère vers l’utilisateur |
| date_commande | DateTime | Date de création de la commande |
| adresse_livraison | String | Adresse de livraison |
| statut | String | Statut: `en_attente`, `validée`, `expédiée`, `annulée` |

## LigneCommande

| Champ | Type | Description |
| --- | --- | --- |
| id | Integer | Clé primaire |
| commande_id | Integer | Clé étrangère vers Commande |
| produit_id | Integer | Clé étrangère vers Produit |
| quantite | Integer | Quantité commandée |
| prix_unitaire | Float | Prix unitaire au moment de la commande |
