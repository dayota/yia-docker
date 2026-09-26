FROM httpd:2.4.68-alpine3.24

COPY yia-health.conf /usr/local/apache2/conf/extra/yia-health.conf

RUN set -eux; \
    sed -i \
      -e 's/^#LoadModule headers_module/LoadModule headers_module/' \
      -e 's/^#LoadModule proxy_module/LoadModule proxy_module/' \
      -e 's/^#LoadModule proxy_fcgi_module/LoadModule proxy_fcgi_module/' \
      -e 's/^#LoadModule proxy_http_module/LoadModule proxy_http_module/' \
      -e 's/^#LoadModule rewrite_module/LoadModule rewrite_module/' \
      /usr/local/apache2/conf/httpd.conf; \
    printf '\nInclude conf/extra/yia-health.conf\nIncludeOptional conf/extra/yia-vhosts.conf\n' \
      >> /usr/local/apache2/conf/httpd.conf; \
    rm -f /usr/local/apache2/htdocs/index.html; \
    printf 'ok\n' > /usr/local/apache2/htdocs/.yia-health; \
    httpd -t
