# --- Stage 1: build a self-contained curl bundle (binary + NON-glibc libs + CA)
FROM registry.access.redhat.com/ubi9/ubi-minimal AS curlbundle

# Ensure CA certs; install curl-minimal only if missing
RUN set -eux; \
    microdnf -y install ca-certificates && microdnf clean all; \
    test -x /usr/bin/curl || (microdnf -y install curl-minimal && microdnf clean all)

# Collect curl and only its non-glibc deps into /out/opt/curl
RUN set -eux; \
    mkdir -p /out/opt/curl/bin /out/opt/curl/lib; \
    # keep the real binary under a different name
    cp -a /usr/bin/curl /out/opt/curl/bin/curl-real; \
    # copy CA bundle if present
    if [ -f /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem ]; then \
      cp -a /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem /out/opt/curl/cacert.pem; \
    elif [ -f /etc/ssl/certs/ca-bundle.crt ]; then \
      cp -a /etc/ssl/certs/ca-bundle.crt /out/opt/curl/cacert.pem; \
    fi; \
    # copy linked libraries but EXCLUDE glibc family and the dynamic loader
    ldd /usr/bin/curl | awk '{print $3}' | grep -E '^/' | \
      while read -r lib; do \
        base="$(basename "$lib")"; \
        case "$base" in \
          libc.so.*|libm.so.*|libdl.so.*|libpthread.so.*|librt.so.*|libresolv.so.*|libnsl.so.*|ld-linux*.so.*) \
            ;; \
          *) cp -L "$lib" "/out/opt/curl/lib/$base" ;; \
        esac; \
      done; \
    # include a few common non-glibc deps if they exist (best-effort)
    for extra in \
      /lib64/libnghttp2.so.* /lib64/libbrotlidec.so.* /lib64/libidn2.so.* \
      /lib64/libpsl.so.* /lib64/libz.so.* /lib64/libssl.so.* /lib64/libcrypto.so.*; do \
      [ -e "$extra" ] && cp -L "$extra" "/out/opt/curl/lib/$(basename "$extra")" || true; \
    done; \
    # create a wrapper that sets LD_LIBRARY_PATH only for curl
    cat > /out/opt/curl/bin/curl <<'SH'
#!/bin/sh
# Use our bundled libs only for this curl invocation
export LD_LIBRARY_PATH="/opt/curl/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
# Use bundled CA if present
[ -f /opt/curl/cacert.pem ] && export CURL_CA_BUNDLE="/opt/curl/cacert.pem"
exec /opt/curl/bin/curl-real "$@"
SH
RUN chmod +x /out/opt/curl/bin/curl

# --- Stage 2: Keycloak image (no package manager)
FROM quay.io/keycloak/keycloak:25.0.6

USER root
# Add the curl bundle under /opt/curl (no touching /lib* or /etc/*)
COPY --from=curlbundle /out/opt/curl /opt/curl

# Make our curl available on PATH (no global LD_LIBRARY_PATH!)
ENV PATH="/opt/curl/bin:${PATH}"

# Your init/start script
COPY scripts/init-and-start.sh /opt/keycloak/init-and-start.sh
RUN chmod +x /opt/keycloak/init-and-start.sh

# Your init/start script
COPY scripts/keycloak_healthcheck.sh /opt/keycloak/healthcheck.sh
RUN chmod +x /opt/keycloak/healthcheck.sh

USER 1000
ENTRYPOINT ["/opt/keycloak/init-and-start.sh"]
