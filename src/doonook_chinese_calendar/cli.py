import click
from alembic import command
from alembic.config import Config
from pathlib import Path
import os
import importlib.resources
from .core.config import settings

@click.group()
def cli():
    """CLI commands for doonook-chinese-calendar"""
    pass

@cli.command()
@click.option('--revision', default='head', help='Revision to upgrade to')
@click.option('--db-url', help='Database URL (overrides settings)')
def migrate(revision, db_url):
    """Run database migrations"""
    # Get the package directory
    package_dir = Path(__file__).parent
    click.echo(package_dir) 
    migrations_dir = package_dir / "migrations"
    
    # Create a config object
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(migrations_dir))
    
    # Use provided DB URL or get from settings
    database_url = db_url or settings.DATABASE_URL
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    
    # Run the migration
    click.echo(f"Running migration to {revision}...")
    command.upgrade(alembic_cfg, revision)
    click.echo("Migration complete!")

if __name__ == '__main__':
    cli() 