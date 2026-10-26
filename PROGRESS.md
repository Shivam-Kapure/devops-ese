# PROGRESS — UPI Payment Settlement Engine (local demonstration)

Every status here is based on real command output. Nothing connects to real UPI networks, banks or production systems.

## Phase 0 — Environment audit (2026-10-26) — DONE, approved

| Item | Result |
|---|---|
| Project dir | `D:\devops lab ese`, empty at audit; not a Git repo |
| Git | 2.47.0.windows.2; global `init.defaultBranch=master` (so use `git init -b main`) |
| Docker | Client/Server 29.7.2 (linux engine), Compose v5.4.0; no `fintech-gateway` container or image; `alpine` not yet pulled; `nginx:alpine` present |
| kubectl | v1.36.1; contexts `docker-desktop`, `kind-project9`, `minikube` (current), `shortly`; all unreachable at audit |
| Minikube | v1.39.0; profile `minikube` (docker driver, containerd) **Stopped**; user will start it before Phase 5 |
| Jenkins | `http://localhost:8080` HTTP 200, Jenkins 2.572, Windows service as LocalSystem; job list needs login (403 anonymous); `docker.exe` on machine PATH and `npipe:////./pipe/docker_engine` responds |
| Terraform | v1.16.6 |
| Ansible | Not on Windows; WSL Ubuntu `ansible [core 2.16.3]`; project path in WSL `/mnt/d/devops lab ese` |
| Java / Python | 25.0.3 LTS / 3.12.4 |
| Ports | 8080 Jenkins; 8081 free; 30091 free (see PORTS.md) |

Decision: Kubernetes target = existing Minikube profile `minikube` (context `minikube`).

## Phase 1 — Project files prepared (2026-10-26)

Created: `gateway.conf`, `Dockerfile`, `Jenkinsfile`, `payment-k8s.yaml`, `main.tf`, `.gitignore`, `PROGRESS.md`, `PORTS.md`.
Nothing built, applied, or committed yet.

Local checks (read-only):
- `gateway.conf` bytes = `SETTLEMENT_CORE=ACTIVE` + LF (23 bytes, no BOM).
- `terraform fmt -check` → exit 0.
- Jenkinsfile Stage 1 `bat` body extracted and run with `cmd`: real project PASS (exit 0); CRLF copy PASS; wrong value / extra line / missing file all FAIL (exit 1).
  - First version used `findstr /x`, which wrongly failed the real LF file; replaced with a PowerShell line comparison that accepts LF or CRLF (`core.autocrlf=true` here, so Git may rewrite endings on checkout).
- `payment-k8s.yaml` not yet validated against a cluster (Minikube stopped).

## Phase 4 (task) — Docker image and container (2026-10-26)

Pre-check: no container named `fintech-gateway`; port 8081 had no listener.

Commands run (from `D:\devops lab ese`):
```powershell
docker pull alpine                    # exit 0, alpine@sha256:be2656061b53...
docker build -t fintech-gateway:v1.0 .   # exit 0
docker run -d --name fintech-gateway -p 8081:80 fintech-gateway:v1.0   # exit 0, id bbfa1a1ed541
docker ps
docker ps -a --filter "name=fintech-gateway"
docker logs fintech-gateway
docker image inspect fintech-gateway:v1.0
```

Results:
- Image: `fintech-gateway:v1.0`, Id `sha256:e18e54b8c760c69fc42cef95197be532248f4ef3919fca66112aff656e0c2dc0`, linux/amd64, Cmd `["echo","Payment Settlement Active"]`, content size 3.86 MB. (`Created` shows 2026-10-21 — the timestamp carried from the alpine base, since the build added no new layers.)
- Container `fintech-gateway` (bbfa1a1ed541): created and ran; `Exited (0)`, ExitCode 0, ran ~0.3 s; port binding recorded `80/tcp -> 8081`.
- `docker logs fintech-gateway` → `Payment Settlement Active`
- `docker ps` → empty (expected: `echo` finishes and the container exits). Port 8081 has no listener afterwards.

Image built ✔ · container created ✔ · container ran and printed expected output ✔ · container still running ✘ (by design of the required CMD).

## Phase 5 (task) — Kubernetes pre-deployment checks (2026-10-26)

- `minikube start -p minikube` (run by Claude at user's request) → exit 0, "Done!". kubectl current-context `minikube` before and after (unchanged).
- `minikube status -p minikube` → host/kubelet/apiserver Running, kubeconfig Configured.
- Node `minikube` Ready, v1.37.0, InternalIP 192.168.67.2, containerd 2.3.4, driver `docker`.
- Namespaces: default, kube-node-lease, kube-public, kube-system.
- Pre-existing, unrelated (left untouched): `default/payment-backend`, `default/payment-frontend` deployments; `payment-backend-service` (ClusterIP), `payment-frontend-service` (NodePort 30099).
- `payment-deployment` / `payment-service`: do not exist. `kubectl get all -A -l tier=payment` → No resources found (selector won't capture other pods).
- NodePorts in use: only 30099 → 30091 free; default range 30000-32767.
- `kubectl --context minikube apply --dry-run=server -f payment-k8s.yaml` → both "created (server dry run)", exit 0.
- `nginx:alpine` not cached on node → will be pulled by the node on first apply.
- Access: 192.168.67.2 not reachable from Windows (TCP to :30099 timed out) → use `minikube service payment-service -p minikube --url` tunnel; `localhost:30091` will NOT work directly.

User approved the first apply.

## Phase 5 (task) — Kubernetes deployment and NodePort (2026-10-26)

```powershell
kubectl --context minikube apply -f payment-k8s.yaml
#   deployment.apps/payment-deployment created
#   service/payment-service created          (exit 0)
kubectl --context minikube rollout status deployment/payment-deployment --timeout=180s
#   deployment "payment-deployment" successfully rolled out   (exit 0)
```

Verification (`--context minikube`, namespace default):
- `get deployments` → `payment-deployment 2/2 2 2`
- `get pods -l tier=payment` → `payment-deployment-745fd4f8d5-bwpfd` 1/1 Running (10.244.0.5), `payment-deployment-745fd4f8d5-p2p2n` 1/1 Running (10.244.0.6), 0 restarts
- `get services` → `payment-service NodePort 10.99.216.189 80:30091/TCP`
- `get all -l tier=payment` → 2 pods Running, service/payment-service 80:30091/TCP, deployment 2/2, replicaset 2/2/2
- `describe service payment-service` → Selector `tier=payment`, Port 80/TCP, TargetPort 80/TCP, NodePort 30091/TCP, Endpoints `10.244.0.5:80,10.244.0.6:80`

Access (docker driver on Windows):
- `minikube service payment-service -p minikube --url` → `http://127.0.0.1:58065` (tunnel; port is random each run, terminal must stay open)
- `Invoke-WebRequest http://127.0.0.1:58065` → HTTP 200, `Server: nginx/1.31.8`, title "Welcome to nginx!"; 4 more requests all 200
- `http://localhost:30091` → timed out (expected; node IP 192.168.67.2 not routable from Windows)
- Tunnel closed afterwards (minikube PID 9076 and its ssh child PID 15960 stopped; port 58065 released).

## Phase 6 (task) — Terraform (2026-10-26)

```powershell
terraform fmt -check                       # exit 0
terraform init                             # exit 0, hashicorp/local v2.9.1 installed, .terraform.lock.hcl created
terraform validate                         # "Success! The configuration is valid." exit 0
terraform plan "-out=payment.tfplan"       # exit 0 — Plan: 1 to add, 0 to change, 0 to destroy
```
- Plan: `+ local_file.payment_env`, filename `./payment.env`, content `URL=http://localhost:30091` + newline.
- Config contains exactly one resource: `resource "local_file" "payment_env"`.
- Note: first `terraform plan -out=payment.tfplan` failed ("Too many command line arguments") because PowerShell 5.1 splits the unquoted `-out=...` argument; quoting fixed it.
- User approved apply.

```powershell
terraform apply "payment.tfplan"
#   local_file.payment_env: Creation complete after 0s [id=dd76e153993fdda524260499823f7e7ac4abea51]
#   Apply complete! Resources: 1 added, 0 changed, 0 destroyed.   (exit 0)
terraform state list                       # local_file.payment_env  (only resource)
terraform plan -detailed-exitcode         # "No changes", exit 0
```
- `payment.env` exists; content `URL=http://localhost:30091` + LF (27 bytes), exact byte comparison True.

### Ansible (WSL Ubuntu, ansible core 2.16.3)
```powershell
wsl -d Ubuntu -- ansible localhost -m command -a "cat '/mnt/d/devops lab ese/payment.env'" -c local
#   localhost | CHANGED | rc=0 >>
#   URL=http://localhost:30091
```
exit 0. (`CHANGED` is normal for the `command` module; rc=0 and output matches.)

## Extension — UPI settlement app (frontend + backend), 2026-10-26

User asked for a real frontend/backend app before Git. Decision (user-approved): **add alongside** — the required root `Dockerfile`, `payment-k8s.yaml` and `main.tf` stay exactly as specified.

New files:
- `backend/` — Flask settlement API (`app.py`): create payment (UPI ID + amount validation, ₹100000 limit, 2-decimal paise, Idempotency-Key), list/get payments, run settlement batch (per-payee-bank net totals), list batches, stats, health. Reads `SETTLEMENT_CORE` (from gateway.conf / ConfigMap); not ACTIVE → 503. In-memory ledger, local demo only.
- `backend/tests/test_app.py` — 19 pytest unit tests. `backend/Dockerfile` — multi-stage (`test` stage runs pytest, `runtime` = gunicorn, non-root uid 10001, HEALTHCHECK).
- `frontend/` — static dashboard (`public/index.html`, `app.js`, `styles.css`) served by `nginx:alpine`; `nginx.conf` proxies `/api/` → `settlement-backend:5000`.
- `docker-compose.yml` — runs both locally on http://localhost:8090.
- `k8s/app-k8s.yaml` — ConfigMap `gateway-config`, Deployment+ClusterIP `settlement-backend` (1 replica: in-memory ledger), Deployment `settlement-frontend` (2 replicas) + NodePort Service 30092. Labels `app: upi-settlement` / `component` — never `tier: payment`.
- `.dockerignore` (root, keeps context small), `backend/.dockerignore`; `.gitignore` += Python caches.
- `Jenkinsfile` updated: Stage 1 = gateway.conf check + backend unit tests (`docker build --target test`); Stage 2 = fintech-gateway:v1.0 (build+inspect, unchanged) + backend + frontend images (build+inspect); Stage 3 = message only (no auto-apply).

Verification:
- `python -m pytest` (local) → **19 passed**; `docker build --target test backend` → **19 passed** inside the image.
- Images built: `upi-settlement-backend:v1.0` (1055edaf2b9e), `upi-settlement-frontend:v1.0` (3e0a3e7d36ea).
- `docker compose up -d` → both containers `Up (healthy)`; frontend `0.0.0.0:8090->80`.
- Through nginx on :8090: `GET /` 200 "UPI Settlement Console"; `/api/health` → `UP`, `settlement_core=ACTIVE`; 3 payments PENDING → `POST /api/settlements/run` → BATCH0001, 3 payments, ₹3660.00, per bank ybl 1349.50 / okhdfcbank 2310.50; stats consistent.
- Browser: dashboard renders; "Add 5 sample payments" button worked via UI JS; no console errors.
- `kubectl apply --dry-run=server -f k8s/app-k8s.yaml` → 5 objects "created (server dry run)".
- `minikube -p minikube image load` for both images → exit 0, listed in `minikube image ls`.
- `kubectl --context minikube apply -f k8s/app-k8s.yaml` → 5 created; rollouts: settlement-backend 1/1, settlement-frontend 2/2 successfully rolled out; `settlement-frontend` NodePort 80:30092.
- Required resources unaffected: `payment-deployment` 2/2, `payment-service` endpoints still only 10.244.0.5, 10.244.0.6.
- In-cluster HTTP test via `minikube service settlement-frontend -p minikube --url` → `http://127.0.0.1:64367`: `GET /` 200 "UPI Settlement Console"; `/api/health` UP, `settlement_core=ACTIVE` (from ConfigMap); payment ₹499.00 PENDING → BATCH0001 settled (ybl ₹499.00); stats consistent. Tunnel and its ssh child stopped, port released.
- Updated Jenkinsfile `bat` blocks run locally through `cmd` (same env vars): block 1 gateway.conf PASS; block 2 backend tests PASS; block 3 built+inspected fintech-gateway, backend, frontend images — all exit 0.
  - Block 2 first reused Docker's cached test layer (pytest not re-executed). Added `--no-cache-filter test` so every pipeline run re-runs pytest; re-run printed `[test 5/5] RUN python -m pytest ...` → `19 passed`.

Note on `fintech-gateway:v1.0`: rebuilt after adding `.dockerignore` → new image ID `df5572c37e22` (was `e18e54b8c760`). Same single layer `sha256:75c137ae…`, same Created, same Cmd — only BuildKit's build-provenance metadata differs. The Docker-task container `fintech-gateway` was run from `e18e54b8c760`. Each Jenkins build will produce another ID for the same content.

## Task status

| Task | Marks | Result | Evidence |
|---|---:|---|---|
| Git release branching and annotated tag | 2 | PENDING | — |
| Jira sprint completion | 1 | PENDING | — |
| Jenkins Declarative Pipeline | 2 | PENDING | — |
| Docker image and container | 2 | PASS | Image `e18e54b8c760` inspected; container `fintech-gateway` Exited (0) with log `Payment Settlement Active` (exit is expected for the required `echo` CMD) |
| Kubernetes deployment and NodePort | 2 | PASS | Rollout succeeded; 2/2 pods Running/Ready; `payment-service` NodePort 80:30091 with 2 endpoints; HTTP 200 nginx via `minikube service` tunnel |
| Terraform and Ansible validation | 1 | PASS | fmt/init/validate/plan OK; apply 1 added; `payment.env` = `URL=http://localhost:30091`; Ansible from WSL rc=0 printed the same line |
