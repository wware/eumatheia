# Eumatheia Implementation Plan

**Purpose:** Detailed, actionable checklist to implement the Kubernetes-based architecture described in `DESIGN_DOC.md`.

**Status tracking:** Use checkboxes `- [ ]` for pending items, `- [x]` for completed work.

---

## Phase 1: Kubernetes Infrastructure Setup

### 1.1 Cluster Setup
- [ ] Choose between `kind` and `minikube` for the shared cluster
- [ ] Document installation/setup steps for target VM (DigitalOcean/AWS)
- [ ] Stand up the cluster on a development machine for testing
- [ ] Verify cluster is accessible and healthy (`kubectl cluster-info`)
- [ ] Add `kubernetes` Python package to `pyproject.toml` dependencies
- [ ] Test basic Kubernetes Python client connectivity

### 1.2 Namespace Template Design
- [ ] Design `ResourceQuota` YAML template for per-session limits
  - [ ] Set CPU limits (e.g., 2 cores max)
  - [ ] Set memory limits (e.g., 4Gi max)
  - [ ] Set storage limits if using PVCs
- [ ] Design `LimitRange` YAML template for per-pod defaults
  - [ ] Default CPU request/limit per container
  - [ ] Default memory request/limit per container
- [ ] Design `NetworkPolicy` YAML template for namespace isolation
  - [ ] Default-deny cross-namespace traffic
  - [ ] Allow egress to external services (or restrict if needed)
- [ ] Design `ServiceAccount` + `Role` + `RoleBinding` template
  - [ ] Scope to namespace-only kubectl access
  - [ ] List allowed API verbs (get, list, create, delete pods/services)
- [ ] Create template files in `manifests/session-templates/`

---

## Phase 2: Namespace Provisioner Module

### 2.1 Replace `container_manager.py`
- [ ] Create new module `src/eumatheia/namespace_manager.py`
- [ ] Implement `NamespaceManager` class
  - [ ] Constructor: initialize Kubernetes client
  - [ ] Method: `create_namespace(session_id: str) -> None`
    - [ ] Create namespace with name `sess-{session_id}`
    - [ ] Apply `ResourceQuota` from template
    - [ ] Apply `LimitRange` from template
    - [ ] Apply `NetworkPolicy` from template
    - [ ] Create `ServiceAccount`, `Role`, `RoleBinding`
  - [ ] Method: `delete_namespace(session_id: str) -> bool`
    - [ ] Delete namespace (cascading delete handles all resources)
  - [ ] Method: `get_namespace_metadata(session_id: str) -> dict`
    - [ ] Return namespace status, age, resource usage
- [ ] Use frozen Pydantic model pattern for metadata (like `Session`)
- [ ] Write unit tests for namespace creation/deletion (mock k8s client)

### 2.2 Wire into orchestrator
- [ ] Update `main.py` global state to use `NamespaceManager` instead of `ContainerManager`
- [ ] Update `lifespan()` to initialize `NamespaceManager`
- [ ] Update `POST /api/sessions` to call `create_namespace()`
- [ ] Update `DELETE /api/sessions` to call `delete_namespace()`
- [ ] Update `reaper_task()` to call `delete_namespace()` for reaped sessions
- [ ] Remove old `container_manager.py` module
- [ ] Update imports throughout codebase

---

## Phase 3: Setup Manifests Application

### 3.1 Implement manifest application
- [ ] Create method in `NamespaceManager`: `apply_setup_manifests(session_id: str, manifests: list[SetupManifest]) -> None`
- [ ] For each manifest in `Exhibit.setup`:
  - [ ] Read manifest file from `exhibits/{exhibit_id}/{manifest.manifest}`
  - [ ] Parse YAML (handle multi-document YAML with `---` separators)
  - [ ] Set namespace field to `sess-{session_id}` for each resource
  - [ ] Apply using Kubernetes Python client (`create_namespaced_*` methods)
  - [ ] Handle idempotency (apply vs. create or patch)
- [ ] Call `apply_setup_manifests()` in `POST /api/sessions` after namespace creation
- [ ] Add error handling for invalid/missing manifest files
- [ ] Test with demo exhibit containing sample manifests

### 3.2 Update exhibit examples
- [ ] Create example Kubernetes manifests for demo exhibits
  - [ ] Simple pod definition for `demo` exhibit
  - [ ] Deployment + Service for `fastapi-crud` exhibit
  - [ ] Add to `exhibits/{exhibit_id}/manifests/` directories
- [ ] Update `exhibit.yaml` files to reference new manifests in `setup:` section
- [ ] Document manifest format and requirements

---

## Phase 4: Per-Session Terminal Pod

### 4.1 Terminal pod provisioning
- [ ] Create gotty pod template YAML in `manifests/session-templates/terminal-pod.yaml`
  - [ ] Container: gotty with bash
  - [ ] ServiceAccount: use namespace's scoped ServiceAccount
  - [ ] Resource requests/limits
  - [ ] Labels for identification (`app=terminal`, `session={session_id}`)
- [ ] Create corresponding Service template for gotty pod
  - [ ] ClusterIP service on port 7681
  - [ ] Selector matching terminal pod labels
- [ ] Add method to `NamespaceManager`: `provision_terminal(session_id: str) -> None`
  - [ ] Apply terminal pod template to namespace
  - [ ] Apply terminal service template
  - [ ] Wait for pod to be Ready (with timeout)
- [ ] Call `provision_terminal()` in `POST /api/sessions` after setup manifests
- [ ] Test terminal pod creation and accessibility

### 4.2 Terminal connectivity
- [ ] Determine service URL pattern for in-cluster access
  - [ ] Format: `terminal-{session_id}.{namespace}.svc.cluster.local:7681`
- [ ] Test WebSocket connection from orchestrator to terminal service
- [ ] Verify gotty is accessible and functional

---

## Phase 5: Per-Session Routing and Reverse Proxy

### 5.1 Update proxy endpoints
- [ ] Replace hardcoded `host.docker.internal:7681` in `proxy_terminal()`
  - [ ] Extract `session_id` from request (URL path or header)
  - [ ] Construct in-cluster service URL: `http://terminal-{session_id}.sess-{session_id}.svc.cluster.local:7681/{path}`
  - [ ] Update proxy target dynamically per session
- [ ] Replace hardcoded `host.docker.internal:9000` in `proxy_app()`
  - [ ] Similar pattern: extract session, route to session's app service
  - [ ] Service name from exhibit config or convention (e.g., `app-{session_id}`)
- [ ] Test proxying to multiple concurrent sessions
- [ ] Handle missing/unavailable services gracefully (return 503)

### 5.2 Session identification
- [ ] Decide how to identify session from request
  - [ ] Option A: URL path includes session ID (`/sess-{id}/terminal/...`)
  - [ ] Option B: Session cookie or header
  - [ ] **Recommendation:** URL path for clarity and debuggability
- [ ] Update proxy endpoints to extract session ID from URL
- [ ] Update frontend to use new URL format for iframe sources
  - [ ] `TerminalPane`: use `/sess-{session_id}/terminal/` as iframe src
  - [ ] `IframePane`: use `/sess-{session_id}/app/{path}` for apps

### 5.3 Frontend updates
- [ ] Update `TerminalPane.tsx` to construct session-specific terminal URL
- [ ] Update `IframePane.tsx` to construct session-specific app URL
- [ ] Test frontend with new routing
- [ ] Rebuild frontend and Docker image

---

## Phase 6: Ancillary Files Integration

### 6.1 Container image building from ancillary Dockerfiles
- [ ] Decide on image build strategy:
  - [ ] Option A: Pre-build images, reference by tag in pod spec
  - [ ] Option B: Build images on-demand per session (slower, more flexible)
  - [ ] **Recommendation:** Pre-build for now, add build-on-demand later
- [ ] For `ancillary.dockerfile` in step definition:
  - [ ] Build image: `docker build -f {dockerfile} -t eumatheia-{exhibit_id}-{step_id}:latest .`
  - [ ] Push to registry (local registry, Docker Hub, or cluster-local registry)
  - [ ] Update pod specs to use built image
- [ ] For `ancillary.compose`:
  - [ ] Parse docker-compose.yml
  - [ ] Generate equivalent Kubernetes manifests (Deployment, Service)
  - [ ] Apply to namespace
- [ ] For `ancillary.scripts`:
  - [ ] Mount as ConfigMap in pod
  - [ ] Make accessible to terminal session

### 6.2 Update provisioning flow
- [ ] When step changes (via `POST /next` or `PUT /step`):
  - [ ] Check if step has `ancillary` files
  - [ ] If Dockerfile changed: rebuild/redeploy pod with new image
  - [ ] If compose changed: update services
  - [ ] If scripts changed: update ConfigMap
- [ ] Handle step transitions gracefully (rolling update vs. full teardown)

---

## Phase 7: Verification System

### 7.1 Shell verification execution
- [ ] Create new endpoint: `POST /api/sessions/{id}/verify`
- [ ] For `verify.type == "shell"`:
  - [ ] Use `kubectl exec` into terminal pod (or designated verify pod)
  - [ ] Run `verify.command` in pod
  - [ ] Capture stdout/stderr
  - [ ] Check if `verify.expect_contains` string is in output
  - [ ] Return `{"passed": bool, "output": str}`
- [ ] Alternative: create short-lived Job for verification
  - [ ] Pros: Isolated from learner's terminal state
  - [ ] Cons: Slower, more complex
  - [ ] **Recommendation:** Start with `kubectl exec`, add Job option later
- [ ] For `verify.type == "manual"`:
  - [ ] Return `{"passed": true}` (user-confirmed via Continue button)

### 7.2 Frontend integration
- [ ] Update `StepNav.tsx` to call verify endpoint when user clicks Next/Continue
- [ ] Show verification status (pending, passed, failed)
- [ ] Display verification output on failure
- [ ] Block advancement if verification fails
- [ ] Test with both shell and manual verify steps

---

## Phase 8: Non-Linear Navigation

### 8.1 Frontend nav button support
- [ ] Update `StepNav.tsx` to check for `step.nav` field
- [ ] If `step.nav` exists:
  - [ ] Render custom buttons instead of Back/Next
  - [ ] Each button calls `PUT /api/sessions/{id}/step` with `target` step ID
  - [ ] Handle special target `"previous"` (use step history)
- [ ] If `step.nav` is null:
  - [ ] Render default Back/Next buttons (existing behavior)
- [ ] Test with `docker-demo` exhibit updated to include nav example

### 8.2 Update exhibits
- [ ] Create example exhibit with branching navigation
- [ ] Add `nav:` section to relevant steps
- [ ] Test all navigation paths
- [ ] Document nav feature in exhibit authoring guide

---

## Phase 9: Session Persistence and Restore

### 9.1 SQLite-backed session store
- [ ] Create SQLite database schema:
  - [ ] Table: `sessions` (session_id, exhibit_id, current_step, created_at, last_activity)
  - [ ] Table: `restore_tokens` (token, session_id, created_at, expires_at)
- [ ] Update `SessionManager` to persist to SQLite instead of in-memory dict
  - [ ] `create_session()` inserts to DB
  - [ ] `get_session()` reads from DB
  - [ ] `update_step()` updates DB
  - [ ] `delete_session()` deletes from DB
  - [ ] `reap_idle_sessions()` queries DB for expired sessions
- [ ] Add database connection to `lifespan()` startup/shutdown
- [ ] Test session persistence across orchestrator restarts

### 9.2 Restore token system
- [ ] Implement `POST /api/sessions/{id}/restore-token`
  - [ ] Generate secure token (e.g., `secrets.token_urlsafe(32)`)
  - [ ] Insert to `restore_tokens` table with expiry (e.g., 7 days)
  - [ ] Return token to user
- [ ] Implement `POST /api/restore?token={token}`
  - [ ] Look up token in DB
  - [ ] Check expiry
  - [ ] Create new namespace for exhibit
  - [ ] Apply setup manifests
  - [ ] Set session to stored `current_step`
  - [ ] Return new session ID
- [ ] Add UI for generating restore link
- [ ] Add UI messaging about restore behavior (fresh namespace, not state snapshot)

---

## Phase 10: Cleanup and Polish

### 10.1 Remove dead code
- [ ] Delete `static/index.html` (superseded by React frontend)
- [ ] Delete `Dockerfile.ttyd`, `Dockerfile.ttyd-source` (superseded by gotty)
- [ ] Delete old `container_manager.py` (replaced by `namespace_manager.py`)
- [ ] Remove unused imports and commented-out code
- [ ] Update `.gitignore` if needed

### 10.2 Naming consistency
- [ ] Decide: `eumatheia` or `Edutopia`?
- [ ] Update FastAPI app title in `main.py`
- [ ] Update `pyproject.toml` description
- [ ] Update all documentation
- [ ] Update frontend title/branding

### 10.3 Documentation
- [ ] Update README.md with current architecture
- [ ] Create exhibit authoring guide
  - [ ] How to write exhibit.yaml
  - [ ] How to create manifests
  - [ ] How to use ancillary files
  - [ ] How to write narrative markdown
- [ ] Document deployment steps for VM setup
- [ ] Document development setup (kind/minikube locally)

### 10.4 Testing
- [ ] Write integration tests for full session lifecycle
  - [ ] Create session → namespace created
  - [ ] Load step → correct panes and narrative
  - [ ] Advance step → step updates
  - [ ] Verify step → verification runs
  - [ ] Delete session → namespace deleted
- [ ] Write tests for multi-session isolation
  - [ ] Create two sessions, verify NetworkPolicy isolation
  - [ ] Verify ResourceQuota enforcement
- [ ] Load testing: how many concurrent sessions can one VM handle?

---

## Phase 11: Deployment to Production VM

### 11.1 VM provisioning
- [ ] Provision VM (DigitalOcean Droplet or AWS EC2)
  - [ ] Recommended: 8 CPU, 16GB RAM, 100GB disk (scale based on testing)
- [ ] Install Docker
- [ ] Install kind or minikube
- [ ] Install Python 3.13
- [ ] Install uv
- [ ] Clone repository

### 11.2 Cluster setup on VM
- [ ] Initialize kind/minikube cluster
- [ ] Verify cluster health
- [ ] Apply any cluster-wide configs (e.g., ingress controller if needed)

### 11.3 Orchestrator deployment
- [ ] Build orchestrator Docker image on VM (or push from CI)
- [ ] Run orchestrator container
  - [ ] Mount kubeconfig for cluster access
  - [ ] Expose port 8000
- [ ] Configure reverse proxy (nginx) if needed for WebSockets
- [ ] Set up SSL/TLS (Let's Encrypt)
- [ ] Test external access

### 11.4 Monitoring and maintenance
- [ ] Set up log aggregation (orchestrator logs, pod logs)
- [ ] Set up basic monitoring (CPU, memory, active sessions)
- [ ] Create alerts for:
  - [ ] Cluster resource exhaustion
  - [ ] Orchestrator downtime
  - [ ] Namespace creation failures
- [ ] Document maintenance procedures
  - [ ] How to restart cluster
  - [ ] How to force-delete stuck namespaces
  - [ ] How to check session health

---

## Open Questions to Resolve

These need decisions before or during implementation:

1. **Cluster choice:** kind vs. minikube?
   - kind: more production-like, better CI integration
   - minikube: simpler, more features out-of-box

2. **Idle timeout and activity tracking:**
   - Current: HTTP hits only, 30 min
   - Better: terminal keystrokes count as activity?
   - How to track terminal activity without polling?

3. **Verification execution:**
   - `kubectl exec` into terminal pod (simpler, faster)
   - Short-lived Job (more isolated, slower)
   - Recommendation: start with exec, measure if state contamination is an issue

4. **Narrative location:**
   - Current: centralized in `narratives/`
   - Alternative: per-exhibit in `exhibits/{id}/narratives/`
   - Decision needed: migrate now or keep centralized?

5. **Ancillary image builds:**
   - Pre-build and tag (faster, less flexible)
   - Build on-demand per session (slower, more flexible)
   - Hybrid: pre-build for common steps, on-demand for custom?

6. **Session routing URL pattern:**
   - Option A: `/sess-{id}/terminal/`, `/sess-{id}/app/`
   - Option B: Session cookie/header, same paths
   - Recommendation: URL path for transparency

7. **Resource limits per namespace:**
   - Need realistic numbers based on load testing
   - Start conservative (2 CPU, 4Gi RAM), adjust based on usage

---

## Success Metrics

How do we know this is working?

- [ ] Can create 10+ concurrent sessions without resource contention
- [ ] Sessions are properly isolated (cannot access each other's resources)
- [ ] Terminal is responsive and persistent across tab switches
- [ ] Verification system correctly passes/fails based on output
- [ ] Idle sessions are reaped after timeout
- [ ] Namespace deletion is clean (no orphaned resources)
- [ ] Can restore to a previous step (not state, but starting point)
- [ ] Frontend works smoothly with real multi-session backend

---

## Timeline Estimates (Rough)

- Phase 1 (Cluster setup): 1-2 days
- Phase 2 (Namespace provisioner): 2-3 days
- Phase 3 (Setup manifests): 1-2 days
- Phase 4 (Terminal pod): 2-3 days
- Phase 5 (Routing): 2-3 days
- Phase 6 (Ancillary files): 3-5 days
- Phase 7 (Verification): 2-3 days
- Phase 8 (Nav): 1 day
- Phase 9 (Persistence): 3-4 days
- Phase 10 (Cleanup): 1-2 days
- Phase 11 (Deployment): 2-3 days

**Total: ~3-4 weeks of focused work**

Note: These are estimates for one experienced developer working full-time. Adjust based on your context.
