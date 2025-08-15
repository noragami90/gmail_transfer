# Gunicorn configuration for Gmail Transfer Tool

import os
import multiprocessing

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', 5000)}"
backlog = 2048

# Worker processes
workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = "eventlet"
worker_connections = int(os.environ.get('GUNICORN_WORKER_CONNECTIONS', 1000))
max_requests = int(os.environ.get('GUNICORN_MAX_REQUESTS', 1000))
max_requests_jitter = int(os.environ.get('GUNICORN_MAX_REQUESTS_JITTER', 50))

# Timeouts
timeout = int(os.environ.get('GUNICORN_TIMEOUT', 120))
keepalive = int(os.environ.get('GUNICORN_KEEPALIVE', 5))

# Logging
accesslog = os.environ.get('GUNICORN_ACCESS_LOG', '-')
errorlog = os.environ.get('GUNICORN_ERROR_LOG', '-')
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'gmail-transfer'

# Server mechanics
daemon = False
pidfile = '/tmp/gunicorn.pid'
user = None
group = None
tmp_upload_dir = None

# SSL
keyfile = os.environ.get('GUNICORN_KEYFILE')
certfile = os.environ.get('GUNICORN_CERTFILE')

# Application
wsgi_module = 'app:app'
preload_app = True
reload = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

# Environment variables
raw_env = [
    f'FLASK_ENV={os.environ.get("FLASK_ENV", "production")}',
    f'PORT={os.environ.get("PORT", 5000)}',
]

def post_fork(server, worker):
    """Called after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_fork(server, worker):
    """Called before a worker is forked."""
    pass

def when_ready(server):
    """Called when the server is ready to receive requests."""
    server.log.info("Gmail Transfer Tool is ready to serve requests")

def worker_int(worker):
    """Called when a worker receives the SIGINT or SIGQUIT signal."""
    worker.log.info("Worker received INT or QUIT signal")

def on_exit(server):
    """Called when gunicorn is about to exit."""
    server.log.info("Gmail Transfer Tool is shutting down")
