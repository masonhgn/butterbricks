FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# each category's data for the site (web/sql/data.json and store.db, web/implementation/problems.json and py/), and web/catalog.json
RUN python build.py

# one process: the sign-in throttle lives in memory, and SQLite on the volume wants a single writer
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--access-logfile", "-"]
