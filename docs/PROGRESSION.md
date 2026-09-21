# Étapes du projet

Afin de terminer le projet, toutes les étapes doivent être complétées.

## Développements des routes API de gestion des utilisateurs

L'application propose deux types de profils.

- **Clients** : Peuvent créer un compte, se connecter, parcourir le catalogue, passer des commandes et suivre l'état de leurs commandes.
- **Administrateurs** : Disposent des droits de gestion du catalogue produits, de suivi et modification des commandes.

La création de compte nécessite une adresse email unique, un mot de passe sécurisé et les informations personnelles de base. Lors de la connexion, l'utilisateur reçoit un token d'authentification lui permettant d'accéder aux fonctionnalités selon son rôle.

- Inscription d'un nouvel utilisateur (`POST /api/auth/register`).
- Connexion et génération de token JWT (`POST /api/auth/login`).

## Développement des routes API de catalogue produits

### Pour les visiteurs et clients

- Navigation dans le catalogue complet des produits.
- Affichage des détails d'un produit (description, prix, disponibilité).
- Recherche de produits par nom ou caractéristiques.

### Pour les administrateurs

- Ajout de nouveaux produits au catalogue.
- Modification des informations produits existants.
- Gestion des stocks.
- Suppression de produits du catalogue.

Chaque produit dispose d'une fiche détaillée incluant son nom, sa description complète, sa catégorie, son prix et sa disponibilité en stock.

- Récupérer la liste des produits (`GET /api/produits`)
- Récupérer un produit spécifique (`GET /api/produits/{id}`)
- Créer un nouveau produit (`POST /api/produits`) - *Admin uniquement*
- Modifier un produit existant (`PUT /api/produits/{id}`) - *Admin uniquement*
- Supprimer un produit (`DELETE /api/produits/{id}`) - *Admin uniquement*

## Développement des routes API de gestion des commandes

### Pour les clients

- Création d'une nouvelle commande
- Ajout de produits au panier avec les quantités souhaitées
- Spécification de l'adresse de livraison
- Consultation de l'historique des commandes
- Suivi de l'état d'avancement d'une commande

### Pour les administrateurs

- Consultation de toutes les commandes de la plateforme
- Modification du statut des commandes (en attente, validée, expédiée, annulée)
- Visualisation détaillée du contenu de chaque commande

Le système doit s'assurer que les produits commandés sont disponibles en stock et mettre à jour automatiquement les quantités disponibles lors de la validation d'une commande.

- Récupérer la liste des commandes (`GET /api/commandes`) - *Admin voit tout, client voit ses commandes*
- Récupérer une commande spécifique (`GET /api/commandes/{id}`)
- Créer une nouvelle commande (`POST /api/commandes`)
- Modifier le statut d'une commande (`PATCH /api/commandes/{id}`) - *Admin uniquement*
- Consulter les lignes d'une commande (`GET /api/commandes/{id}/lignes`)
