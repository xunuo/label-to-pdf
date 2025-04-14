FROM python:3.12.9 AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app


RUN python -m venv .venv
COPY requirements.txt ./
RUN .venv/bin/pip install -r requirements.txt
FROM python:3.12.9-slim
WORKDIR /app
COPY --from=builder /app/.venv .venv/
COPY . .
CMD ["/app/.venv/bin/flask", "run", "--host=0.0.0.0", "--port=8000"]
# CMD ["/app/.venv/bin/gunicorn", "-b", "0.0.0.0:8080", "main:app"]


# Use gunicorn to serve t
# CMD ["/app/.venv/bin/gunicorn", "-b", "0.0.0.0:8080", "main:app"]

