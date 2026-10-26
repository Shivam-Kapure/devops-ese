# UPI settlement backend. `--target test` runs the unit tests; the default target is the runtime image.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM base AS test
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY app.py .
COPY tests ./tests
RUN python -m pytest -q -p no:cacheprovider tests

FROM base AS runtime
COPY app.py .
RUN useradd --system --uid 10001 settlement
USER 10001
ENV SETTLEMENT_CORE=ACTIVE PORT=5000
EXPOSE 5000
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=2).status == 200 else 1)"
# One worker keeps the in-memory ledger consistent; threads handle concurrent requests.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "--access-logfile", "-", "app:app"]
