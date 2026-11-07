# syntax=docker/dockerfile:1

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build

COPY package.json ./
COPY scripts/frontend.cjs scripts/frontend.cjs
COPY frontend/.npmrc frontend/package.json frontend/package-lock.json frontend/
RUN npm --prefix frontend ci

COPY frontend ./frontend
RUN npm run frontend:build

FROM python:3.11-slim-bookworm AS runtime
ARG VERSION=0.0.0
ARG VCS_REF=unknown
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 shanque \
    && useradd --uid 10001 --gid shanque --no-create-home --shell /usr/sbin/nologin shanque \
    && mkdir /data \
    && chown shanque:shanque /data

COPY run.py ./run.py
COPY workspace ./workspace
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
COPY LICENSE NOTICE ./
COPY frontend/LICENSE ./third-party/ant-design-pro/LICENSE
LABEL org.opencontainers.image.title="山雀企业项目工作台" \
      org.opencontainers.image.description="面向团队协作的企业项目跟踪工作台" \
      org.opencontainers.image.source="https://github.com/ffbum/shanque" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.revision=$VCS_REF

USER 10001:10001
EXPOSE 5086
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5086/api/session', timeout=3)" || exit 1
ENTRYPOINT ["python", "run.py", "--server", "--host", "0.0.0.0", "--port", "5086", "--data-dir", "/data"]
