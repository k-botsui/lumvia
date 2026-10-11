from logging.config import fileConfig

from alembic import context
from app import models  # noqa: F401
from app.db import Base, engine

fileConfig(context.config.config_file_name)
if context.is_offline_mode():
    context.configure(url=str(engine.url), target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
