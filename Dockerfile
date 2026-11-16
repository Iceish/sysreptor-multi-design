# Build the pinned upstream base first with scripts/dev.sh build.
ARG SYSREPTOR_BASE=multidesign-upstream:6b0b1fcf
FROM node:24.22.1-bookworm-slim AS frontend
WORKDIR /build
COPY sysreptor-src/packages sysreptor-src/packages
WORKDIR /build/sysreptor-src/packages
RUN npm ci
WORKDIR /build
COPY custom_plugins/multidesign/frontend custom_plugins/multidesign/frontend
WORKDIR /build/custom_plugins/multidesign/frontend
RUN npm ci && npm run generate

FROM ${SYSREPTOR_BASE}
USER 0
COPY examples /examples
COPY custom_plugins/multidesign /custom_plugins/multidesign
COPY --from=frontend /build/custom_plugins/multidesign/static /custom_plugins/multidesign/static
ENV PLUGIN_DIRS=/app/plugins,/custom_plugins
USER 1000
