FROM python:3.12.12-slim-bookworm

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends gosu; \
    rm -rf /var/lib/apt/lists/*; \
    groupadd --gid 1000 yia; \
    useradd --uid 1000 --gid yia --create-home yia

COPY entrypoint.sh /usr/local/bin/yia-python-entrypoint
COPY develop.sh /usr/local/bin/yia-python-develop
COPY python-healthcheck.py /usr/local/lib/yia/python-healthcheck.py

RUN chmod 0755 /usr/local/bin/yia-python-entrypoint /usr/local/bin/yia-python-develop

WORKDIR /workspace
ENTRYPOINT ["yia-python-entrypoint"]
CMD ["yia-python-develop"]
