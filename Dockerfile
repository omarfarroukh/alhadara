# Use official Python base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set workdir inside container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install pip requirements
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy project code
COPY . /app/

# Collect static files if needed (optional, can be run manually or in entrypoint)
# RUN python manage.py collectstatic --noinput

# Expose Django port

CMD ["uvicorn", "alhadara.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
