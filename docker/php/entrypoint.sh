#!/bin/sh
set -eu

yia_uid="${YIA_UID:-1000}"
yia_gid="${YIA_GID:-1000}"

case "$yia_uid" in
    ''|*[!0-9]*)
        echo "YIA_UID must be a positive integer" >&2
        exit 64
        ;;
esac
case "$yia_gid" in
    ''|*[!0-9]*)
        echo "YIA_GID must be a positive integer" >&2
        exit 64
        ;;
esac
if [ "$yia_uid" -eq 0 ] || [ "$yia_gid" -eq 0 ]; then
    echo "YIA_UID and YIA_GID must be greater than zero" >&2
    exit 64
fi

current_uid="$(id -u yia)"
current_gid="$(id -g yia)"
if [ "$current_gid" != "$yia_gid" ]; then
    groupmod -o -g "$yia_gid" yia
fi
if [ "$current_uid" != "$yia_uid" ] || [ "$current_gid" != "$yia_gid" ]; then
    usermod -o -u "$yia_uid" -g "$yia_gid" yia
fi
chown yia:yia /home/yia

for vendor_directory in /workspace/*/vendor; do
    if [ -d "$vendor_directory" ]; then
        chown yia:yia "$vendor_directory"
    fi
done

case "${1:-}" in
    php-fpm|php-fpm*)
        exec docker-php-entrypoint "$@"
        ;;
    *)
        exec su-exec yia docker-php-entrypoint "$@"
        ;;
esac
