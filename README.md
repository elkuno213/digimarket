# DigiMarket API

DigiMarket is a Flask REST API project using SQLite, SQLAlchemy, and JWT authentication.

## Start the application

Run these steps from the `python/` directory.

1. Install the locked dependencies and create the local virtual environment:

   ```bash
   uv sync
   ```

2. Create a local `.env` file with the required, non-empty configuration:

   ```dotenv
   DATABASE_PATH=/absolute/path/to/digimarket.db
   JWT_SECRET_KEY=replace-with-a-long-private-secret
   ```

3. Start the development server:

   ```bash
   uv run flask run --debug
   ```

Flask automatically discovers the `app` package and its `create_app` factory. At the M0 foundation stage, no public routes exist yet, so a `404 Not Found` response is expected.

## Work on the project

Use these commands during development:

```bash
uv run pytest
uv run ruff format --check app tests
uv run ruff check app tests
uv run mypy app
```

When dependencies change, use `uv add <package>` for a runtime dependency, `uv add --dev <package>` for a development dependency, or `uv remove <package>` to remove one. These commands update `pyproject.toml`, `uv.lock`, and the local environment; commit the first two files together.

Use `uv lock --upgrade` only when you intentionally want newer versions of the locked dependencies.

## Project documentation

- [Roadmap and design](docs/DESIGN.md)
- [Project description](docs/DESCRIPTION.md)
- [Data structures](docs/STRUCTURE-DES-DONNEES.md)
- [Milestone progression](docs/PROGRESSION.md)
