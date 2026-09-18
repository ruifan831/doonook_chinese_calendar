"""Run the real calendar routes with an isolated, temporary database.

Usage: python run_local.py --env-file .env.local --port 8008
Only model / calendar API settings are loaded from that file. PostgreSQL
deployment settings are deliberately excluded from this local test process.
"""

import argparse
import os
from pathlib import Path
import tempfile

from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env.local"))
    parser.add_argument("--port", type=int, default=8008)
    args = parser.parse_args()
    if not args.env_file.is_file():
        parser.error("找不到配置文件，请通过 --env-file 指定本地测试 .env 文件")

    values = dotenv_values(args.env_file)
    for name in (
        "QWEN_BASE_URL",
        "QWEN_LAN_API_KEY",
        "QWEN_MODEL",
        "ASTRO_EPHEMERIS_PATH",
        "QWEN_TIMEOUT_SECONDS",
        "TIMEZONE",
        "LANGUAGE",
        "JISU_API_KEY",
    ):
        # The chosen file, rather than a stale exported deployment value, wins.
        if values.get(name) is not None:
            os.environ[name] = values[name]
        else:
            os.environ.pop(name, None)
    for name in ("QWEN_BASE_URL", "QWEN_LAN_API_KEY", "QWEN_MODEL"):
        if not os.environ.get(name, "").strip():
            parser.error(f"测试配置缺少 {name}")

    # Package import creates its normal engine but must never connect to a
    # business database. All routes below override its writer dependency.
    os.environ.update(
        ASTRO_GENERATE_ON_REQUEST="true",  # Isolated model smoke testing only.
        POSTGRES_USER="unused",
        POSTGRES_PASSWORD="unused",
        POSTGRES_HOST="127.0.0.1",
        POSTGRES_PORT="1",
        POSTGRES_DB="unused",
        DOONOOK_NODE_ROLE="primary",
        REMOTE_WRITER_HOST="",
    )

    import uvicorn
    from fastapi import FastAPI
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from doonook_chinese_calendar import create_calendar_router
    from doonook_chinese_calendar.core.database import Base, get_db_writer

    app = FastAPI(title="Chinese Calendar 本机测试")
    app.include_router(create_calendar_router())

    from datetime import date as Date
    import asyncio
    from fastapi import HTTPException
    from doonook_chinese_calendar.core.config import settings
    from doonook_chinese_calendar.services.astro_basis import (
        build_basis,
        EphemerisError,
    )

    @app.get("/debug/astro-basis/{astroid}", tags=["本机占星依据"])
    async def inspect_basis(astroid: int, date: Date):
        if not 1 <= astroid <= 12:
            raise HTTPException(422, "星座编号应为1至12")
        try:
            return await asyncio.to_thread(
                build_basis,
                astroid,
                date,
                settings.ASTRO_EPHEMERIS_PATH,
                settings.TIMEZONE,
            )
        except EphemerisError as exc:
            raise HTTPException(503, str(exc)) from None

    with tempfile.TemporaryDirectory(prefix="calendar-local-") as directory:
        engine = create_engine(
            "sqlite:///" + str(Path(directory) / "calendar.sqlite"),
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine)

        def test_db():
            with Session(engine) as session:
                yield session

        app.dependency_overrides[get_db_writer] = test_db
        print(f"Swagger: http://127.0.0.1:{args.port}/docs", flush=True)
        print("数据库：临时 SQLite；退出后删除。Qwen：读取指定 .env 文件。", flush=True)
        try:
            uvicorn.run(app, host="127.0.0.1", port=args.port)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
