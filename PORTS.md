# Ports — UPI Payment Settlement Engine (local demo)

Checked 2026-10-26 with `Get-NetTCPConnection -LocalPort <port> -State Listen`.

| Port | Status at audit | Owner | Purpose in this case study |
|---:|---|---|---|
| 8080 | LISTEN on `::` | PID 5392 `java` — Jenkins 2.572 Windows service (LocalSystem, `D:\jenkins`) | Jenkins UI for `payment-settlement-pipeline` (pre-existing, not changed) |
| 8081 | Free (re-checked before `docker run`) | Docker — container `fintech-gateway`, only while it runs | Host side of `docker run -p 8081:80`. Binding `80/tcp -> 8081` is recorded, but the container exits after `echo`, so 8081 had no listener afterwards (verified) |
| 30091 | Free on host; free in cluster before apply (only 30099 used) | `default/payment-service` NodePort in `minikube` cluster (node 192.168.67.2) | Exposes nginx pods. Not reachable as `localhost:30091` on Windows (verified: timeout); use the tunnel below |
| 8090 | Free before; now LISTEN | Docker — `upi-settlement-frontend` (docker compose) | Local UPI Settlement Console + `/api` proxy → `upi-settlement-backend:5000` (backend not published to host) |
| 30092 | Free in cluster before apply | `default/settlement-frontend` NodePort in `minikube` | UPI Settlement Console in Kubernetes; reach via `minikube service settlement-frontend -p minikube --url` |
| 30099 | In use inside cluster | `default/payment-frontend-service` — pre-existing, unrelated | Not touched |
| 58065 (random) | Used only during test, then released | `minikube service ... --url` tunnel (ssh `-L 58065:10.99.216.189:80`) | Host access to `payment-service`; a new random port is chosen each run |
