# Keycloak (local dev)

1. Start services: `docker compose up -d keycloak`
2. Visit Keycloak at `http://localhost:8081` (admin/admin)
3. Create a realm named **oss**
4. Create a public client **osss-web**
   - Valid redirect URIs: `http://localhost:5173/*`
   - Web origins: `http://localhost:5173`
5. (Optional) Add realm roles: ADMIN, CLERK, MEMBER, PUBLIC

For dev, the API accepts tokens issued to `osss-web` (audience). In production you may prefer a separate confidential client for the API.
