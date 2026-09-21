# Description du projet

La description du projet permet de fournir tout un ensemble d'information par rapport au contexte et au secteur cible. Certaines informations essentielles, comme les contraintes du projet ou encore les objectifs à atteindre, y sont définies.

---

L'entreprise DigiMarket, spécialisée dans la vente de matériels informatique, souhaite diversifier son activité en proposant une boutique en ligne (E-commerce). Pour cela, elle cherche à développer dans un premier temps une API REST, ce qui devra lui permettre la gestion des produits, des catégories, des commandes et des utilisateurs pour une plateforme e-commerce standard, avec un système d'authentification.

En tant que développeur Python, vous êtes sollicité pour **concevoir l'API REST de la boutique en ligne**, en respectant un cahier des charges sur les actions possibles, et sur la manière dont les données vont être stockées en base. Vous devrez développer cette API REST avec le **framework Flask**, et en utilisant **SQLALchemy comme ORM avec une base SQLite**, qui fera office de base de données.

## Contraintes

Pour le projet, il est nécessaire d'utiliser les technologies suivantes.

- **Langage**: Python.
- **Framework backend**: Flask.
- **Base de données** : SQLite avec SQLAlchemy comme ORM.
- **Authentification**: JWT (JSON Web Tokens). On stockera les utilisateurs dans une table SQL.

## Fonctionnalités de l'application

## Gestion des utilisateurs

L'application propose deux types de profils.

- **Clients** : Peuvent créer un compte, se connecter, parcourir le catalogue, passer des commandes et suivre l'état de leurs commandes.
- **Administrateurs** : Disposent des droits de gestion du catalogue produits, de suivi et modification des commandes.

La création de compte nécessite une adresse email unique, un mot de passe sécurisé et les informations personnelles de base. Lors de la connexion, l'utilisateur reçoit un token d'authentification lui permettant d'accéder aux fonctionnalités selon son rôle.

- Inscription d'un nouvel utilisateur (`POST /api/auth/register`).
- Connexion et génération de token JWT (`POST /api/auth/login`).

## Catalogue produits

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

## Gestion des commandes

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

## Exigences techniques

L'application doit suivre une architecture modulaire.

- Séparation claire entre les modèles, les contrôleurs et les vues (JSON).
- Organisation en modules fonctionnels à l'aide des Blueprints Flask.
- Implémentation des bonnes pratiques REST.

### Sécurité et authentification

- Authentification sécurisée via tokens JWT.
- Hachage des mots de passe.
- Vérification des autorisations selon le rôle utilisateur.
- Protection contre les injections SQL et autres vulnérabilités courantes.

### Qualité du code

- Code bien structuré et commenté.
- Gestion appropriée des erreurs et exceptions.
- Tests unitaires et fonctionnels.
- Documentation complète de l'API.

## Livrables attendus

1. **Code source**

   - Structure de projet claire et organisée
   - Fichier `requirements.txt` listant toutes les dépendances

2. **Application fonctionnelle** avec toutes les fonctionnalités demandées

3. **Documentation technique (README.md)**:

   - Instructions d'installation et d'utilisation
   - Description des fonctionnalités
   - Documentation de l'API

4. **Base de données** initialisée avec des données de test

5. **Tests** couvrant les principales fonctionnalités
