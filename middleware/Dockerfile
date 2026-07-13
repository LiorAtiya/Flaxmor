# Python 3.11 — the assignment's minimum version, pinned exactly.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/middleware

# Install the package (prod dependencies only — no pytest/respx in the image).
# Known trade-off: copying `app` before install means a code change re-installs
# dependencies. Accepted for simplicity — the full build takes well under a minute.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# Run as a non-root user (best practice: a compromised process can't touch the system).
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
