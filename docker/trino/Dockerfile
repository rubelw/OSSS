# Base
FROM trinodb/trino:latest

USER root
WORKDIR /etc/trino

# Copy Trino configs (includes /etc/trino/keystore/* you already manage)
COPY config_files/trino/etc /etc/trino/


# or set via jvm.config; if you use env, keep this:
ENV JAVA_TOOL_OPTIONS="-Djavax.net.ssl.trustStore=/etc/trino/keystore/truststore.jks \
 -Djavax.net.ssl.trustStorePassword=changeit \
 -Djavax.net.ssl.trustStoreType=JKS"

USER trino
