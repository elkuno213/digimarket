"""Trusted local administrator onboarding command."""

import click
from flask import Flask

from app.auth.service import (
    AdministratorAlreadyExistsError,
    DuplicateEmailError,
    ValidationError,
    onboard_administrator,
)


def register_onboarding_command(app: Flask) -> None:
    """Register the explicit command that creates DigiMarket's first administrator."""
    app.cli.add_command(onboard_command)


@click.command("onboard")
@click.option("--email", envvar="ADMIN_EMAIL", required=True)
@click.option("--name", envvar="ADMIN_NAME", required=True)
@click.option("--password", envvar="ADMIN_PASSWORD", required=True)
def onboard_command(email: str, name: str, password: str) -> None:
    """Create the first administrator from trusted local command input."""
    try:
        administrator = onboard_administrator(email, name, password)
    except (AdministratorAlreadyExistsError, DuplicateEmailError, ValidationError) as error:
        raise click.ClickException(str(error)) from error

    click.echo(f"Administrator onboarded: {administrator.email}")
