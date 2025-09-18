# OSSS Kubernetes Manifests (Kustomize)

This directory mirrors the core `docker-compose.yml` services for local development using Kubernetes:

Included services:
- `api` (FastAPI) -> port 8081
- `web` (Next.js) -> port 3000
- `postgres` (backend DB) -> port 5432 (nodePort may differ)
- `keycloak` (auth) -> port 8080 (container) / Service 8080 (external)
- `keycloak-postgres` (Keycloak DB) -> port 5432
- `redis` (cache/queue) -> port 6379

Optional add-ons (templates provided, commented in `kustomization.yaml`):
- `ingress` (HTTP routing for web/api/keycloak) via Traefik/NGINX
- `secrets` (sample: **do not commit real secrets**)
- `persistent volumes` using default StorageClass (customize to your cluster)

## Quick start (kind / minikube)

```bash
# From repo root (after cloning OSSS), copy this folder into ./k8s
# or replace existing k8s with this one.

# Create namespace + apply base stack
kubectl apply -k k8s/

# Port-forward for local dev:
kubectl -n osss port-forward svc/web 3000:3000 &
kubectl -n osss port-forward svc/api 8081:8081 &
kubectl -n osss port-forward svc/keycloak 8080 &
```

If your images are not in a registry, build + load them into the cluster (kind/minikube) so `imagePullPolicy: IfNotPresent` can find them locally:

```bash
# Example image tags used by these manifests:
# - osss-api:dev
# - osss-web:dev

# Build from your monorepo (adjust Dockerfile contexts as needed)
docker build -t osss-api:dev -f docker/api/Dockerfile .
docker build -t osss-web:dev -f docker/web/Dockerfile .

# Load into kind
kind load docker-image osss-api:dev
kind load docker-image osss-web:dev
```

## Environment variables

The manifests use reasonable defaults and map a subset of env from `.env/.env.example`.
You can edit the `config/configmap.yaml` and `secrets/secrets.sample.yaml` to match your local dev.

## Notes

- For production, switch to a managed Postgres and external Keycloak DB.
- Replace `emptyDir` with proper PVCs and set requests/limits to your infra.
- Consider Helm or a top-level Skaffold for image builds/watch in dev.


---

## Add-ons: Elasticsearch, Kibana, Consul (DEV)

This repo includes manifests for a single-node dev Elasticsearch + Kibana and a single-server Consul with UI.

### Quick start (enable all add-ons with an overlay)
```bash
kubectl apply -k k8s/overlays/addons
# Port-forward (optional)
kubectl -n osss port-forward svc/elasticsearch 9200:9200 &
kubectl -n osss port-forward svc/kibana 5601:5601 &
kubectl -n osss port-forward svc/consul 8500:8500 &
```

### Security & persistence
- **Elasticsearch**: `xpack.security.enabled=false` for dev only. For prod, enable security, set passwords, TLS, and proper storage (PVC).
- **Kibana**: No auth in this dev setup. Configure auth in prod and point to secured ES.
- **Consul**: Dev mode with `-ui` and no ACLs. For prod, run a server cluster, enable ACLs, and consider the Consul Helm chart.

### DNS (Consul)
This sample exposes Consul DNS on UDP/8600 via a ClusterIP Service, which won't be reachable from host by default.
If you need DNS on your host, add a NodePort/hostNetwork or run a local DNS forwarder.



### Vault (dev)

This package also includes a Vault dev server manifest.

```bash
kubectl apply -k k8s/overlays/addons

# Port-forward to access UI/API
kubectl -n osss port-forward svc/vault 8200:8200 &

# Root token for dev mode
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=root
```

⚠️ **Note**: This runs Vault with `-dev` mode: ephemeral storage, single node, no HA, root token in plaintext.  
For production: use persistent storage (Raft or external), enable TLS, and secure tokens/policies properly.


### Vault (DEV)
- Runs in **dev mode** with UI enabled, listens on 8200, and uses a fixed root token (`root`). This is for local testing only.
- For production: use integrated storage (Raft) with a StatefulSet and enable init/unseal (e.g., via KMS auto-unseal). Consider using the official HashiCorp Helm chart.

**Port-forward**
```bash
kubectl -n osss port-forward svc/vault 8200:8200 &
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=root
```

**Keycloak OIDC (example quick start)**
After Keycloak is up and you have a realm/client, you can enable OIDC auth in Vault (dev mode):
```bash
vault auth enable oidc
vault write auth/oidc/config   oidc_discovery_url="http://keycloak8080/realms/OSSS"   oidc_client_id="vault"   oidc_client_secret="<client-secret>"   default_role="osss"

vault write auth/oidc/role/osss   user_claim="preferred_username"   allowed_redirect_uris="http://localhost:8200/ui/vault/auth/oidc/oidc/callback"   allowed_redirect_uris="http://vault:8200/ui/vault/auth/oidc/oidc/callback"   policies="default"
```
