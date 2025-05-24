web: daphne alhadara.asgi:application --port $PORT --bind 0.0.0.0 --proxy-headers
worker: celery -A alhadara worker --loglevel=info