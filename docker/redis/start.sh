#!/bin/sh
set -eu

if [ -n "${REDIS_PASSWORD_FILE:-}" ]; then
    . /yia/read-secret.sh
    REDIS_PASSWORD="$(yia_read_secret "$REDIS_PASSWORD_FILE")" || exit 2
fi

# Keep the secret out of server arguments and persistent data. Redis ACLs
# accept SHA-256 hashes, so quoting and special characters need no encoding.
if [ -z "${REDIS_PASSWORD:-}" ]; then
    printf '%s\n' 'REDIS_PASSWORD must be set and non-empty' >&2
    exit 2
fi
umask 077
acl_file="$(mktemp /tmp/yia-redis-acl.XXXXXX)"
password_hash="$(printf '%s' "$REDIS_PASSWORD" | sha256sum)"
printf 'user default reset on #%s ~* &* +@all\n' "${password_hash%% *}" > "$acl_file"
chown redis:redis "$acl_file"
unset REDIS_PASSWORD password_hash

# Delegate volume ownership and privilege dropping to the official image.
exec /usr/local/bin/docker-entrypoint.sh redis-server \
    --aclfile "$acl_file" --dir /data \
    --appendonly yes --appendfsync everysec --save '900 1 300 10 60 10000'
