from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = None  # raw SQL migrations only

def run_migrations_offline():
    url = context.get_x_argument(as_dictionary=True).get("sqlalchemy_url") or config.get_main_option("sqlalchemy.url")
    if not url:
        import os
        url = os.getenv("TUTOR_DB_URL")
    if not url:
        raise RuntimeError("TUTOR_DB_URL (or -x sqlalchemy_url) not set")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    import os
    url = os.getenv("TUTOR_DB_URL") or config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("TUTOR_DB_URL not set")
    engine = create_engine(url, poolclass=pool.NullPool, future=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
