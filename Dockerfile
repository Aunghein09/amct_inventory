FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files (uses whitenoise manifest)
RUN SECRET_KEY=build-placeholder python manage.py collectstatic --noinput

EXPOSE 8080

ENTRYPOINT ["./entrypoint.sh"]
