#!/bin/sh
set -eu

package_manager="${YIA_PACKAGE_MANAGER:-pnpm}"
node_port="${YIA_NODE_PORT:-}"

if [ ! -f package.json ]; then
    echo "Node application requires package.json in $(pwd)" >&2
    exit 66
fi

case "$package_manager" in
    pnpm)
        export PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false
        if [ -f pnpm-lock.yaml ]; then
            pnpm install \
                --frozen-lockfile \
                --store-dir /home/node/.local/share/pnpm/store
        else
            pnpm install \
                --no-lockfile \
                --store-dir /home/node/.local/share/pnpm/store
        fi
        if [ -n "$node_port" ]; then
            exec pnpm run dev --host 0.0.0.0 --port "$node_port"
        fi
        exec pnpm run dev
        ;;
    npm)
        if [ -f package-lock.json ] || [ -f npm-shrinkwrap.json ]; then
            npm ci
        else
            npm install --no-package-lock
        fi
        if [ -n "$node_port" ]; then
            exec npm run dev -- --host 0.0.0.0 --port "$node_port"
        fi
        exec npm run dev
        ;;
    yarn)
        if [ -f yarn.lock ]; then
            yarn install --frozen-lockfile
        else
            yarn install --no-lockfile
        fi
        if [ -n "$node_port" ]; then
            exec yarn run dev --host 0.0.0.0 --port "$node_port"
        fi
        exec yarn run dev
        ;;
    *)
        echo "Unsupported Node package manager: $package_manager" >&2
        exit 64
        ;;
esac
