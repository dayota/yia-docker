FROM node:22.23.3-bookworm

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        gosu \
        openssh-client; \
    rm -rf /var/lib/apt/lists/*; \
    npm install --global --force pnpm@11.27.1 yarn@1.22.22; \
    node --version; \
    npm --version; \
    pnpm --version; \
    yarn --version

COPY entrypoint.sh /usr/local/bin/yia-node-entrypoint
COPY develop.sh /usr/local/bin/yia-node-develop
COPY node-healthcheck.js /usr/local/lib/yia/node-healthcheck.js

RUN chmod 0755 /usr/local/bin/yia-node-entrypoint /usr/local/bin/yia-node-develop

WORKDIR /workspace

ENTRYPOINT ["yia-node-entrypoint"]
CMD ["yia-node-develop"]
