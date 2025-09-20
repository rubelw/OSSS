# gunicorn.conf.py
import multiprocessing
import os
import logging

# import path to the app factory (we set PYTHONPATH=/app/src in the Dockerfile)
wsgi_app = "OSSS.api:create_app"
factory = True

# networking
host = os.getenv("HOST", "0.0.0.0")
port = int(os.getenv("PORT", "8000"))
bind = f"{host}:{port}"

# workers
workers = int(os.getenv("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
threads = int(os.getenv("GUNICORN_THREADS", "1"))
worker_tmp_dir = "/dev/shm"
preload_app = True

# timeouts
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# logging
accesslog = "-"   # stdout
errorlog  = "-"   # stderr
loglevel = os.getenv("LOG_LEVEL", "info")
capture_output = True
# help a little with noisy clients
limit_request_field_size = 8190
limit_request_line = 4094

# resiliency on occasional worker leaks
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))

# --- NEW: logging config used by Gunicorn master *and* workers ---
LOG_FMT = "%(asctime)s %(levelname)s %(name)s %(message)s %(process)d %(thread)d %(module)s %(pathname)s"
logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "fmt": LOG_FMT,
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        }
    },
    "root": {"level": os.getenv("LOG_LEVEL", "INFO").upper(), "handlers": ["console"]},
    "loggers": {
        # keep uvicorn logs
        "uvicorn":        {"level": "INFO", "handlers": ["console"], "propagate": False},
        "uvicorn.error":  {"level": "INFO", "handlers": ["console"], "propagate": False},
        "uvicorn.access": {"level": "INFO", "handlers": ["console"], "propagate": False},

        # 🔇 silence the noisy names
        "watchfiles":         {"level": "ERROR", "handlers": ["console"], "propagate": False},
        "watchfiles.main":    {"level": "ERROR", "handlers": ["console"], "propagate": False},
        "watchfiles.watcher": {"level": "ERROR", "handlers": ["console"], "propagate": False},
    },
}

# --- belt & suspenders: enforce after fork too (app may reconfigure logging) ---
def post_fork(server, worker):
    for name in ("watchfiles", "watchfiles.watcher"):
        lg = logging.getLogger(name)
        lg.setLevel(100)      # higher than CRITICAL
        lg.propagate = False
        lg.handlers.clear()

