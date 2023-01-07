import multiprocessing

from gevent import monkey

wsgi_app = 'derailed.app:app'
loglevel = 'info'
proxy_allow_ips = '*'
bind = ['0.0.0.0:8080']
backlog = 1024
workers = (2 * multiprocessing.cpu_count()) + 1
worker_class = 'gevent'
monkey.patch_all()
