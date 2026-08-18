FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# daphne serves both HTTP and websockets (ASGI)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
