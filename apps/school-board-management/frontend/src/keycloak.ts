import Keycloak from "keycloak-js";

const url = import.meta.env.VITE_KEYCLOAK_URL || "http://localhost:8081";
const realm = import.meta.env.VITE_KEYCLOAK_REALM || "oss";
const clientId = import.meta.env.VITE_KEYCLOAK_CLIENT_ID || "osss-web";

export const keycloak = new Keycloak({ url, realm, clientId });
