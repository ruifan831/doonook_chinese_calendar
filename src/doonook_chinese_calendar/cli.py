import click
from alembic import command
from alembic.config import Config
from pathlib import Path
from .core.config import settings


@click.group()
def cli():
    """CLI commands for doonook-chinese-calendar"""
    pass


@cli.command()
@click.option("--revision", default="head", help="Revision to upgrade to")
@click.option("--db-url", help="Database URL (overrides settings)")
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
    alembic_cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

    # Run the migration
    click.echo(f"Running migration to {revision}...")
    command.upgrade(alembic_cfg, revision)
    click.echo("Migration complete!")


@cli.command("warm-astro")
@click.option(
    "--date",
    "target_date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="预生成日期，默认北京时间今天",
)
@click.option(
    "--sign",
    type=click.IntRange(1, 12),
    multiple=True,
    help="星座编号，可重复；默认全部12个",
)
def warm_astro(target_date, sign):
    """顺序生成并缓存运势；已存在的日期/星座不覆盖。"""
    import asyncio
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from .core.database import WriterSessionLocal
    from .services.astro_service import AstroService

    target = (target_date or datetime.now(ZoneInfo(settings.TIMEZONE))).date()

    async def run():
        service = AstroService()
        for astroid in sign or range(1, 13):
            with WriterSessionLocal() as db:
                await service.get_daily_fortune(astroid, target, db)
            click.echo(f"ready: {target} sign={astroid}")

    try:
        asyncio.run(run())
    except Exception:
        raise click.ClickException(
            "运势预生成失败；已完成记录保留，可稍后重试"
        ) from None


if __name__ == "__main__":
    cli()
