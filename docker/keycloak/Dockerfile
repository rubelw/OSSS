# docker/keycloak/Dockerfile
FROM quay.io/keycloak/keycloak:25.0.6

USER root

COPY scripts/init-and-start.sh /opt/keycloak/init-and-start.sh

USER 1000


ENTRYPOINT ["/opt/keycloak/init-and-start.sh"]
