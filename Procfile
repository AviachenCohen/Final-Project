web: WORKER=false gunicorn app:app
worker: WORKER=true celery -A app.celery worker --loglevel=info


