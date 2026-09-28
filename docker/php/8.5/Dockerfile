FROM composer:2.10.3 AS composer

FROM php:8.5.11-fpm-alpine3.24

RUN set -eux; \
    apk add --no-cache \
        bash \
        git \
        icu-libs \
        libpq \
        libzip \
        oniguruma \
        openssh-client \
        shadow \
        su-exec \
        unzip; \
    apk add --no-cache --virtual .yia-build-deps \
        $PHPIZE_DEPS \
        icu-dev \
        libpq-dev \
        libzip-dev \
        linux-headers \
        oniguruma-dev; \
    docker-php-ext-install -j"$(nproc)" \
        bcmath \
        intl \
        mbstring \
        pcntl \
        pdo_mysql \
        pdo_pgsql \
        zip; \
    php -r 'exit(extension_loaded("Zend OPcache") ? 0 : 1);'; \
    pecl install xdebug-3.5.3; \
    docker-php-ext-enable xdebug; \
    apk del .yia-build-deps; \
    rm -rf /tmp/pear

COPY --from=composer /usr/bin/composer /usr/local/bin/composer
COPY entrypoint.sh /usr/local/bin/yia-php-entrypoint
COPY xdebug.ini /usr/local/etc/php/conf.d/99-yia-xdebug.ini
COPY default-pool.conf /usr/local/etc/php-fpm.d/yia-pools.conf
COPY global.conf /usr/local/etc/php-fpm.d/zz-yia-global.conf

RUN set -eux; \
    addgroup -g 1000 yia; \
    adduser -D -u 1000 -G yia -h /home/yia -s /bin/sh yia; \
    chmod 0755 /usr/local/bin/yia-php-entrypoint; \
    rm -f \
        /usr/local/etc/php-fpm.d/docker.conf \
        /usr/local/etc/php-fpm.d/www.conf \
        /usr/local/etc/php-fpm.d/www.conf.default \
        /usr/local/etc/php-fpm.d/zz-docker.conf; \
    php-fpm -t; \
    composer --version

WORKDIR /workspace

ENTRYPOINT ["yia-php-entrypoint"]
CMD ["php-fpm"]
