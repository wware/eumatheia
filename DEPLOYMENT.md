# Eumatheia Deployment Guide

## Current Status: Phases 1-5, 7 (backend), 9, 10 Complete ✅

The orchestrator is successfully deployed and running in a Kubernetes cluster with:
- Full session lifecycle management
- SQLite-backed persistence (sessions survive orchestrator restarts)
- Shell and manual verification endpoints
- Session restore tokens (7-day expiry)
- Namespace isolation and resource management

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  kind Kubernetes Cluster (gitops-lab)                      │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ eumatheia-system namespace                             │ │
│  │                                                         │ │
│  │  ┌──────────────────────────────────────┐              │ │
│  │  │ Orchestrator Pod                     │              │ │
│  │  │  - FastAPI backend                   │              │ │
│  │  │  - React frontend (built-in)         │              │ │
│  │  │  - ServiceAccount: eumatheia-orch... │              │ │
│  │  │  - Port: 8000                        │              │ │
│  │  └──────────────────────────────────────┘              │ │
│  │         │                                               │ │
│  │         │ (ClusterRole permissions)                     │ │
│  │         ▼                                               │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Session Namespaces (sess-XXXXXXXX)                     │ │
│  │                                                         │ │
│  │  Per session (isolated):                               │ │
│  │  ┌──────────────┐  ┌──────────────┐                    │ │
│  │  │ Terminal Pod │  │ Terminal Svc │                    │ │
│  │  │  - ttyd      │  │  port: 7681  │                    │ │
│  │  │  - bash      │  └──────────────┘                    │ │
│  │  └──────────────┘                                       │ │
│  │                                                         │ │
│  │  ResourceQuota: 2 CPU, 4Gi RAM                         │ │
│  │  LimitRange: Container defaults                        │ │
│  │  NetworkPolicy: Namespace isolation                    │ │
│  │  RBAC: Scoped ServiceAccount                           │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Deployment Steps

### Prerequisites
- kind cluster running (gitops-lab)
- kubectl configured
- Docker installed

### Build and Deploy

```bash
# 1. Build the orchestrator image
docker build -f Dockerfile.orchestrator -t eumatheia-orchestrator:latest .

# 2. Load into kind cluster
kind load docker-image eumatheia-orchestrator:latest --name gitops-lab

# 3. Deploy to Kubernetes
kubectl apply -f manifests/orchestrator/

# 4. Verify deployment
kubectl get pods -n eumatheia-system
kubectl get svc -n eumatheia-system

# 5. Access via port-forward (for local testing)
kubectl port-forward -n eumatheia-system svc/orchestrator 8080:8000
```

### Access
- **Local (port-forward)**: http://localhost:8080
- **Future (production)**: Will use Ingress with proper domain/TLS

## Session Lifecycle

1. **User clicks "Start Demo"** on frontend
2. **Session creation** (`POST /api/sessions`):
   - Generate unique session ID (8 hex chars)
   - Create namespace `sess-{session_id}`
   - Apply ResourceQuota, LimitRange, NetworkPolicy
   - Create ServiceAccount with RBAC
   - Apply exhibit setup manifests (terminal pod + service)
   - Set session cookie (HttpOnly, 30min expiry)
3. **User interaction**:
   - Terminal iframe loads `/terminal/`
   - Proxy extracts session ID from cookie
   - Routes to `http://terminal.sess-{session_id}.svc.cluster.local:7681`
   - Updates session activity timestamp
4. **Session cleanup**:
   - Idle timeout: 30 minutes (configurable)
   - Reaper task runs every 60 seconds
   - Deletes namespace (cascades all resources)

## RBAC Permissions

The orchestrator ServiceAccount has ClusterRole permissions to:
- Create/delete namespaces
- Manage resources within ANY namespace:
  - Pods, Services, ConfigMaps, Secrets, PVCs
  - ServiceAccounts, Roles, RoleBindings
  - NetworkPolicies
  - Deployments, StatefulSets, Jobs
  - ResourceQuotas, LimitRanges

## Key Files

- `Dockerfile.orchestrator` - Multi-stage build (Node.js + Python)
- `manifests/orchestrator/` - Kubernetes deployment manifests
  - `namespace.yaml` - eumatheia-system namespace
  - `rbac.yaml` - ServiceAccount, ClusterRole, ClusterRoleBinding
  - `deployment.yaml` - Deployment + NodePort Service
- `manifests/session-templates/` - Templates for session namespaces
  - `resource-quota.yaml` - Resource limits per session
  - `limit-range.yaml` - Container defaults
  - `network-policy.yaml` - Namespace isolation
  - `service-account.yaml` - Session-scoped RBAC
- `exhibits/*/terminal-pod.yaml` - Per-exhibit terminal configurations
- `exhibits/*/terminal-service.yaml` - Terminal service definitions

## Testing

Run the Phase 3 and Phase 4 test scripts:

```bash
# Test namespace provisioning and manifest application
uv run python test_phase3.py

# Test terminal pod with ttyd
uv run python test_phase4.py
```

## Known Issues / TODO

1. **Frontend features**: Verification UI, restore token UI, non-linear navigation (Phases 7.2, 8, 9.2)
2. **Ancillary files**: Docker image building from compose/Dockerfiles (Phase 6)
3. **Terminal activity tracking**: Currently tracks proxy requests, not actual keystrokes
4. **Production deployment**: Need Ingress, TLS, proper DNS (Phase 11)
5. **Monitoring**: No metrics or alerting yet (Phase 11)
6. **NodePort limitation**: For kind access, production needs LoadBalancer/Ingress
7. **Database persistence**: SQLite DB is ephemeral in pod, needs PersistentVolume for production

## Bug Fixes Applied

1. **Double sess- prefix**: Fixed session_manager to generate IDs without prefix
2. **RBAC permissions**: Added serviceaccounts to ClusterRole resources
3. **Naming consistency**: Unified on "Eumatheia" (was mixed with "Edutopia")

## Completed Phases

- **Phase 1-5**: Orchestrator deployment, session management, namespace provisioning ✅
- **Phase 7 (backend)**: Shell verification endpoint with kubectl exec ✅
- **Phase 9**: SQLite session persistence and restore tokens ✅
- **Phase 10**: Cleanup and naming consistency ✅

## Next Steps (Phase 6, 8, Frontend work)

- Phase 6: Ancillary Files Integration (Docker image building from compose/Dockerfiles)
- Phase 7.2: Frontend verification UI (call verify endpoint, show results)
- Phase 8: Non-Linear Navigation (nav buttons support in frontend)
- Phase 9.2: Frontend restore UI (generate/display restore links)
- Phase 11: Production deployment (PersistentVolume, Ingress, TLS, monitoring)
