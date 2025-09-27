# --- Stage 1: build self-contained curl and jq bundles (binaries + NON-glibc libs + CA)
FROM registry.access.redhat.com/ubi9/ubi-minimal AS curlbundle

# Ensure CA certs; install curl-minimal and jq if missing
RUN set -eux; \
    microdnf -y install ca-certificates && microdnf clean all; \
    test -x /usr/bin/curl || (microdnf -y install curl-minimal && microdnf clean all); \
    test -x /usr/bin/jq   || (microdnf -y install jq && microdnf clean all)

# ---- curl bundle
RUN set -eux; \
    mkdir -p /out/opt/curl/bin /out/opt/curl/lib; \
    cp -a /usr/bin/curl /out/opt/curl/bin/curl-real; \
    if [ -f /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem ]; then \
      cp -a /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem /out/opt/curl/cacert.pem; \
    elif [ -f /etc/ssl/certs/ca-bundle.crt ]; then \
      cp -a /etc/ssl/certs/ca-bundle.crt /out/opt/curl/cacert.pem; \
    fi; \
    ldd /usr/bin/curl | awk '{print $3}' | grep -E '^/' | \
      while read -r lib; do \
        base="$(basename "$lib")"; \
        case "$base" in \
          libc.so.*|libm.so.*|libdl.so.*|libpthread.so.*|librt.so.*|libresolv.so.*|libnsl.so.*|ld-linux*.so.*) ;; \
          *) cp -L "$lib" "/out/opt/curl/lib/$base" ;; \
        esac; \
      done; \
    for extra in \
      /lib64/libnghttp2.so.* /lib64/libbrotlidec.so.* /lib64/libidn2.so.* \
      /lib64/libpsl.so.* /lib64/libz.so.* /lib64/libssl.so.* /lib64/libcrypto.so.*; do \
      [ -e "$extra" ] && cp -L "$extra" "/out/opt/curl/lib/$(basename "$extra")" || true; \
    done; \
    cat > /out/opt/curl/bin/curl <<'SH'
#!/bin/sh
export LD_LIBRARY_PATH="/opt/curl/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
[ -f /opt/curl/cacert.pem ] && export CURL_CA_BUNDLE="/opt/curl/cacert.pem"
exec /opt/curl/bin/curl-real "$@"
SH
RUN chmod +x /out/opt/curl/bin/curl

# ---- jq bundle (same idea)
RUN set -eux; \
    mkdir -p /out/opt/jq/bin /out/opt/jq/lib; \
    cp -a /usr/bin/jq /out/opt/jq/bin/jq-real; \
    ldd /usr/bin/jq | awk '{print $3}' | grep -E '^/' | \
      while read -r lib; do \
        base="$(basename "$lib")"; \
        case "$base" in \
          libc.so.*|libm.so.*|libdl.so.*|libpthread.so.*|librt.so.*|libresolv.so.*|libnsl.so.*|ld-linux*.so.*) ;; \
          *) cp -L "$lib" "/out/opt/jq/lib/$base" ;; \
        esac; \
      done; \
    # include common extras if present
    for extra in /lib64/libonig.so.* /lib64/libjq.so.* /lib64/libz.so.*; do \
      [ -e "$extra" ] && cp -L "$extra" "/out/opt/jq/lib/$(basename "$extra")" || true; \
    done; \
    cat > /out/opt/jq/bin/jq <<'SH'
#!/bin/sh
export LD_LIBRARY_PATH="/opt/jq/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec /opt/jq/bin/jq-real "$@"
SH
RUN chmod +x /out/opt/jq/bin/jq

# --- Stage 2: Keycloak image (no package manager)
FROM quay.io/keycloak/keycloak:25.0.6

USER root
# Add the curl & jq bundles under /opt (no touching /lib* or /etc/*)
COPY --from=curlbundle /out/opt/curl /opt/curl
COPY --from=curlbundle /out/opt/jq   /opt/jq

# Put our tools on PATH (no global LD_LIBRARY_PATH!)
ENV PATH="/opt/curl/bin:/opt/jq/bin:${PATH}"

# Your init/start scripts
COPY scripts/kc-init-and-start.sh /opt/keycloak/init-and-start.sh
RUN chmod +x /opt/keycloak/init-and-start.sh

COPY scripts/keycloak_healthcheck.sh /opt/keycloak/healthcheck.sh
RUN chmod +x /opt/keycloak/healthcheck.sh

USER 1000
ENTRYPOINT ["/opt/keycloak/init-and-start.sh"]
