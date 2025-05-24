web: daphne alhadara.asgi:application --port $PORT --bind 0.0.0.0 --proxy-headers --workers 2
worker: celery -A alhadara worker --loglevel=info