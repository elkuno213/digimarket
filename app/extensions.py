"""Unbound Flask extension instances shared by DigiMarket modules."""

from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

# These objects are not attached to a Flask application until create_app() calls init_app().
db = SQLAlchemy()
jwt = JWTManager()
