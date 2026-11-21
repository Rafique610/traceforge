# Build context: lab/ (the package dir is `worker/`). Two stages, slim non-root runtime.
FROM python:3.12-slim AS build
WORKDIR /build
COPY worker/pyproject.toml .
RUN python -m venv /opt/venv \
    && python -c "import tomllib;print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > requirements.txt \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH=/opt/venv/bin:$PATH
RUN useradd --system --uid 10001 --no-create-home app
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY worker ./worker
USER 10001
CMD ["python", "-m", "worker.main"]
