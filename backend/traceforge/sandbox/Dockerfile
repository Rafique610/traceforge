# Minimal sandbox test image. Test code is mounted at run time, never baked in,
# so one image serves every base_sha with the same dependencies (D30 warm image).
FROM python:3.12-slim
ARG REQS="pytest==8.3.4"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN pip install ${REQS} && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin sandbox
USER 10001:10001
WORKDIR /work
