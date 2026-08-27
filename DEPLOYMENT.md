# Eumatheia Deployment Guide

## Current Status: Phases 1-5 Complete ✅

The orchestrator is successfully deployed and running in a Kubernetes cluster with full end-to-end functionality.

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

1. **Session persistence**: Sessions are in-memory, lost on orchestrator restart (Phase 9)
2. **Terminal activity tracking**: Currently tracks proxy requests, not actual keystrokes
3. **Production deployment**: Need Ingress, TLS, proper DNS (Phase 11)
4. **Monitoring**: No metrics or alerting yet (Phase 11)
5. **NodePort limitation**: For kind access, production needs LoadBalancer/Ingress

## Bug Fixes Applied

1. **Double sess- prefix**: Fixed session_manager to generate IDs without prefix
2. **RBAC permissions**: Added serviceaccounts to ClusterRole resources

## Next Steps (Phase 6+)

- Phase 6: Ancillary Files Integration (Docker image building)
- Phase 7: Verification System (kubectl exec for shell verification)
- Phase 8: Non-Linear Navigation (nav buttons in frontend)
- Phase 9: Session Persistence (SQLite for session state)
- Phase 10: Additional exhibits
- Phase 11: Production deployment
