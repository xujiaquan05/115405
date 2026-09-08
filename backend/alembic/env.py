from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from dotenv import load_dotenv

from alembic import context

# 專案的模型與連線設定：讓 autogenerate 能比對出差異。
load_dotenv()

import os  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.models import database_models  # noqa: F401,E402  匯入以註冊所有資料表

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    """決定 autogenerate 要不要管某個資料庫物件。

    專案有一批索引不是由 SQLAlchemy 模型建立的：
    - database/init.sql 建的 idx_articles_* 效能索引
    - startup.py 建的 pg_trgm GIN 索引（模型層無法表達 gin_trgm_ops）

    autogenerate 只看模型，會把這些判定為「多餘」而產生 drop_index，
    實際跑下去會刪掉效能索引（實測關鍵字查詢從 9ms 退回 228ms）。
    因此這裡明確排除它們，交由既有機制維護。
    """
    if type_ == "index" and name and name.startswith("idx_"):
        return False

    return True


def get_url() -> str:
    """連線字串一律取自 .env，不要寫死在 alembic.ini（避免密碼進版控）。"""
    url = os.getenv("DATABASE_URL")

    if not url:
        raise RuntimeError("DATABASE_URL 未設定，請確認 backend/.env。")

    return url

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
