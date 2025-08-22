# gunicorn.conf.py
import multiprocessing
import os

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
