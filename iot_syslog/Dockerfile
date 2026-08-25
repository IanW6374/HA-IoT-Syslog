# https://developers.home-assistant.io/docs/apps/configuration#app-dockerfile
ARG BUILD_FROM=ghcr.io/home-assistant/base:3.23
FROM ${BUILD_FROM}

RUN apk add --no-cache \
    python3 \
    py3-aiohttp \
    py3-cryptography

COPY rootfs /
RUN chmod a+x \
    /etc/services.d/iot-syslog/run \
    /etc/services.d/iot-syslog/finish

ARG BUILD_VERSION
ARG BUILD_ARCH
LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}" \
    org.opencontainers.image.title="Home Assistant App: IoT Syslog" \
    org.opencontainers.image.description="Encrypted, searchable syslog collection for IoT devices" \
    org.opencontainers.image.source="https://github.com/IanW6374/HA-IoT-Syslog" \
    org.opencontainers.image.licenses="MIT"
