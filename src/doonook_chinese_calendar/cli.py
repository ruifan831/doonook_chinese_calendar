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
@click.option(
    "--days",
    type=click.IntRange(1, 31),
    default=1,
    show_default=True,
    help="从目标日期开始连续预生成的天数，包含当天",
)
def warm_astro(target_date, sign, days):
    """顺序补齐缓存；单条失败继续处理，已有记录不覆盖。"""
    import asyncio
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from .services.astro_prefetch import prefetch

    target = (target_date or datetime.now(ZoneInfo(settings.TIMEZONE))).date()
    try:
        result = asyncio.run(
            prefetch(target, days, tuple(sign or range(1, 13)), report=click.echo)
        )
    except Exception:
        raise click.ClickException(
            "运势预生成失败；已完成记录保留，可稍后重试"
        ) from None
    if result.failed:
        raise click.ClickException(
            f"{len(result.failed)} 条未完成；已完成记录保留，重跑自动补缺"
        )


@cli.command("maintain-astro")
@click.option(
    "--days",
    type=click.IntRange(1, 31),
    default=7,
    show_default=True,
    help="滚动预生成天数，包含当天",
)
@click.option(
    "--interval",
    type=click.IntRange(60, 86400),
    default=3600,
    show_default=True,
    help="每轮结束后等待秒数；失败记录在下一轮补齐",
)
def maintain_astro(days, interval):
    """持续维护未来缓存，交由 systemd/容器监管；只启动一个实例。"""
    import asyncio
    from .services.astro_prefetch import maintain

    try:
        asyncio.run(maintain(days, interval, report=click.echo))
    except KeyboardInterrupt:
        click.echo("预生成已停止；已完成记录保留")


if __name__ == "__main__":
    cli()
