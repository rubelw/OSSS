# config_files/superset/superset_config.py
SECRET_KEY = "please_change_me"  # any random string
SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://osss:osss@postgres-superset:5432/superset"

# Optional but nice:
ENABLE_PROXY_FIX = True
# Use Redis for rate-limit storage to silence in-memory warnings (db 1 reserved for limiter)
RATELIMIT_STORAGE_URI = "redis://superset_redis:6379/1"
