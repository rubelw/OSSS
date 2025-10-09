FROM mysql:8.0-debian
USER root
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends iproute2 net-tools procps \
 && rm -rf /var/lib/apt/lists/*
USER mysql
