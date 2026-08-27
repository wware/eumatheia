# Eumatheia Implementation Plan

**Purpose:** Detailed, actionable checklist to implement the Kubernetes-based architecture described in `DESIGN_DOC.md`.

**Status tracking:** Use checkboxes `- [ ]` for pending items, `- [x]` for completed work.

---

## Phase 1: Kubernetes Infrastructure Setup

### 1.1 Cluster Setup ✅
- [x] **DECISION: Use kind** (see Open Questions - RESOLVED)
- [ ] Document kind installation steps for target VM (DigitalOcean/AWS)
- [x] Stand up kind cluster on development machine for testing (using existing `kind-gitops-lab`)
- [x] Verify cluster is accessible and healthy (`kubectl cluster-info`)
- [x] Add `kubernetes` Python package to `pyproject.toml` dependencies
- [x] Test basic Kubernetes Python client connectivity

### 1.2 Namespace Template Design ✅
- [x] Design `ResourceQuota` YAML template for per-session limits
  - [x] **DECISION: 2 CPU, 4Gi RAM** (start conservative, see Open Questions - RESOLVED)
  - [x] Set CPU limits: 2 cores max
  - [x] Set memory limits: 4Gi max
  - [x] Set storage limits if using PVCs (10Gi max)
- [x] Design `LimitRange` YAML template for per-pod defaults
  - [x] Default CPU request/limit per container (100m request, 500m limit)
  - [x] Default memory request/limit per container (256Mi request, 1Gi limit)
- [x] Design `NetworkPolicy` YAML template for namespace isolation
  - [x] Default-deny cross-namespace traffic
  - [x] Allow egress to external services (HTTP/HTTPS)
- [x] Design `ServiceAccount` + `Role` + `RoleBinding` template
  - [x] Scope to namespace-only kubectl access
  - [x] List allowed API verbs (get, list, create, delete pods/services)
- [x] Create template files in `manifests/session-templates/`
  - [x] `resource-quota.yaml`
  - [x] `limit-range.yaml`
  - [x] `network-policy.yaml`
  - [x] `service-account.yaml` (includes Role and RoleBinding)

---

## Phase 2: Namespace Provisioner Module ✅

### 2.1 Replace `container_manager.py` ✅
- [x] Create new module `src/eumatheia/namespace_manager.py`
- [x] Implement `NamespaceManager` class
  - [x] Constructor: initialize Kubernetes client (with fallback to kubeconfig)
  - [x] Method: `create_namespace(session_id: str) -> dict`
    - [x] Create namespace with name `sess-{session_id}`
    - [x] Apply `ResourceQuota` from template
    - [x] Apply `LimitRange` from template
    - [x] Apply `NetworkPolicy` from template
    - [x] Create `ServiceAccount`, `Role`, `RoleBinding`
  - [x] Method: `delete_namespace(session_id: str) -> None`
    - [x] Delete namespace (cascading delete handles all resources)
  - [x] Method: `get_namespace_metadata(session_id: str) -> dict | None`
    - [x] Return namespace status, age, labels
  - [x] Method: `list_active_sessions() -> list[dict]`
- [x] Helper method `_load_template()` for template processing
- [ ] Use frozen Pydantic model pattern for metadata (like `Session`)
- [ ] Write unit tests for namespace creation/deletion (mock k8s client)

### 2.2 Wire into orchestrator ✅
- [x] Update `main.py` global state to use `NamespaceManager` instead of `ContainerManager`
- [x] Update `lifespan()` to initialize `NamespaceManager`
- [x] Update `POST /api/sessions` to call `create_namespace()`
- [x] Update `DELETE /api/sessions` to call `delete_namespace()`
- [x] Update `reaper_task()` to call `delete_namespace()` for reaped sessions
- [x] Remove old `container_manager.py` module
- [x] Update imports throughout codebase

---

## Phase 3: Setup Manifests Application ✅

**Note:** Narratives migrated to per-exhibit directories (see Phase 3.2).

### 3.1 Implement manifest application ✅
- [x] Create method in `NamespaceManager`: `apply_setup_manifests(session_id: str, exhibit_dir: Path, manifest_files: list[str]) -> None`
- [x] For each manifest in `Exhibit.setup`:
  - [x] Read manifest file from `exhibits/{exhibit_id}/{manifest.manifest}`
  - [x] Parse YAML (handle multi-document YAML with `---` separators)
  - [x] Set namespace field to `sess-{session_id}` for each resource
  - [x] Apply using Kubernetes Python client (`create_namespaced_*` methods)
  - [x] Handle idempotency (409 errors treated as success)
  - [x] Support for Pod, Service, ConfigMap, Secret, PVC, Deployment, StatefulSet, Job
- [x] Call `apply_setup_manifests()` in `POST /api/sessions` after namespace creation
- [x] Add error handling for invalid/missing manifest files with rollback
- [x] Test with demo exhibit containing sample manifests (test_phase3.py verified end-to-end)

### 3.2 Migrate narratives and update exhibit examples ✅
- [x] **DECISION: Migrate narratives to per-exhibit** (see Open Questions - RESOLVED)
- [x] Create `exhibits/{exhibit_id}/narratives/` directories
- [x] Move narratives from `narratives/` to respective exhibit directories:
  - [x] `narratives/hello-world.md` → `exhibits/demo/narratives/hello-world.md`
  - [x] `narratives/try-vim.md` → `exhibits/demo/narratives/try-vim.md`
  - [x] `narratives/docker-*.md` → `exhibits/docker-demo/narratives/`
  - [x] `narratives/fastapi-*.md` → `exhibits/fastapi-crud/narratives/`
- [x] Update `Step.narrative` paths in all `exhibit.yaml` files to be relative
  - [x] Changed from `narrative: narratives/hello-world.md` to `narrative: hello-world.md`
- [x] Update `main.py` narrative loading to resolve from `exhibits/{exhibit_id}/narratives/`
- [x] Delete empty `narratives/` directory at project root
- [x] Create example Kubernetes manifests for demo exhibits
  - [x] `demo/terminal-pod.yaml` - Ubuntu with basic tools (vim, curl, git)
  - [x] `docker-demo/terminal-pod.yaml` - Docker-in-Docker with privileged mode
  - [x] `fastapi-crud/terminal-pod.yaml` - Python 3.12 with FastAPI/uvicorn
- [x] Update `exhibit.yaml` files to reference new manifests in `setup:` section
- [ ] Document manifest format and requirements

---

## Phase 4: Per-Session Terminal Pod ✅

**Note:** Terminal activity tracking implemented via proxy endpoint (updates session timestamp on every request).

### 4.1 Terminal pod provisioning ✅
- [x] **DECISION: Use ttyd instead of gotty** (more modern, better maintained)
- [x] Update exhibit terminal pod manifests to run ttyd on port 7681
  - [x] demo: tsl0922/ttyd:alpine with bash, vim, curl, wget, git
  - [x] docker-demo: docker:24-dind with ttyd binary, privileged mode
  - [x] fastapi-crud: python:3.12-slim with ttyd binary, FastAPI pre-installed
  - [x] All use session-user ServiceAccount
  - [x] Appropriate resource requests/limits per exhibit
- [x] Create terminal-service.yaml for each exhibit
  - [x] ClusterIP service on port 7681
  - [x] Selector: app=eumatheia, component=terminal
- [x] Terminal provisioning handled via exhibit setup manifests
  - [x] No separate provision_terminal() method needed
  - [x] Exhibit.setup includes both terminal-pod.yaml and terminal-service.yaml
- [x] Test terminal pod creation and accessibility (test_phase4.py verified)

### 4.2 Terminal connectivity ✅
- [x] Determined service URL pattern for in-cluster access
  - [x] Format: `terminal.sess-{session_id}.svc.cluster.local:7681`
- [x] Updated proxy_terminal() endpoint in main.py:
  - [x] Extract session_id from cookie or X-Session-ID header
  - [x] Verify session exists
  - [x] Route to in-cluster service URL dynamically
  - [x] Update session activity timestamp on every request
- [x] Implemented session cookie on session creation
  - [x] HttpOnly cookie for security
  - [x] 30 minute expiry matching idle timeout
  - [x] SameSite=Lax for CSRF protection
- [x] Test verified ttyd is accessible and port is exposed correctly

### 4.3 Terminal activity tracking (for idle timeout) ✅
- [x] **DECISION: Option B - Track activity at proxy level**
- [x] Implemented in proxy_terminal() endpoint
  - [x] Calls session_manager.update_activity() on every terminal request
  - [x] WebSocket traffic to terminal counts as activity
  - [x] Terminal keystrokes automatically extend session lifetime
- [ ] Future enhancement: Test that terminal usage prevents idle timeout in practice

---

## Phase 5: Per-Session Routing and Reverse Proxy ✅

### 5.1 Update proxy endpoints ✅
- [x] Replace hardcoded `host.docker.internal:7681` in `proxy_terminal()` (completed in Phase 4)
  - [x] Extract `session_id` from cookie or X-Session-ID header
  - [x] Construct in-cluster service URL: `http://terminal.sess-{session_id}.svc.cluster.local:7681/{path}`
  - [x] Update proxy target dynamically per session
- [x] Replace hardcoded `host.docker.internal:9000` in `proxy_app()`
  - [x] Same pattern: extract session_id from cookie/header
  - [x] Route to `http://app.sess-{session_id}.svc.cluster.local:9000/{path}`
  - [x] Service name convention: 'app' for application services
- [ ] Test proxying to multiple concurrent sessions (requires in-cluster deployment)
- [x] Handle missing/unavailable services gracefully (returns 502 Bad Gateway)

### 5.2 Session identification ✅
- [x] **DECISION: Option B - Session cookie/header** (see Open Questions - RESOLVED)
- [x] Implement session cookie on session creation (`POST /api/sessions`)
  - [x] Set HttpOnly cookie with session_id
  - [x] 30 minute expiry matching idle timeout
  - [x] SameSite=Lax for CSRF protection
- [x] Update proxy endpoints to extract session ID from cookie/header
  - [x] Reads session ID from cookie or `X-Session-ID` header
  - [x] Validates session exists before proxying
  - [x] Updates activity timestamp on every request
- [x] Frontend automatically sends cookies with requests
  - [x] Cookies sent by browser to all endpoints
  - [x] Iframe requests include cookies from parent
- [x] Keep iframe URLs simple (no session ID in path)
  - [x] `TerminalPane`: uses `/terminal/` as iframe src
  - [x] `IframePane`: uses `/app/{path}` for apps

### 5.3 Frontend updates
- [x] TerminalPane already uses `/terminal/` endpoint
- [x] IframePane already uses `/app/` endpoint
- [ ] Test frontend with deployed orchestrator (requires Phase 6)
- [ ] Rebuild frontend and Docker image (part of Phase 6)

---

## Phase 6: Ancillary Files Integration

### 6.1 Container image building from ancillary Dockerfiles
- [ ] **DECISION: Hybrid approach** (see Open Questions - RESOLVED)
  - [ ] Pre-build and tag for common/stable steps
  - [ ] Build on-demand for custom/experimental steps
  - [ ] Check for pre-built tag first, fall back to build
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
- [ ] **DECISION: Use kubectl exec** (see Open Questions - RESOLVED)
- [ ] Create new endpoint: `POST /api/sessions/{id}/verify`
- [ ] For `verify.type == "shell"`:
  - [ ] Use `kubectl exec` into terminal pod
  - [ ] Run `verify.command` in pod
  - [ ] Capture stdout/stderr
  - [ ] Check if `verify.expect_contains` string is in output
  - [ ] Return `{"passed": bool, "output": str}`
- [ ] Monitor for state contamination issues
  - [ ] If learner's terminal state affects verification, add Job-based option later
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

## Open Questions - RESOLVED

Decisions made for implementation:

1. **Cluster choice: kind** ✅
   - More production-like, better CI integration
   - Use kind for both development and production

2. **Idle timeout and activity tracking:** ✅
   - Terminal keystrokes DO count as activity
   - Implementation challenge: need to track activity without polling
   - Possible approach: gotty logs/events, or WebSocket message timestamps
   - **TODO:** Research gotty activity tracking mechanisms

3. **Verification execution: kubectl exec** ✅
   - Use `kubectl exec` into terminal pod (simpler, faster)
   - Measure if state contamination becomes an issue
   - Can add Job-based verification later if needed

4. **Narrative location: migrate now** ✅
   - Move narratives from centralized `narratives/` to per-exhibit directories
   - New structure: `exhibits/{id}/narratives/{filename}.md`
   - Update `Step.narrative` path resolution to be exhibit-relative
   - Keeps all exhibit content together

5. **Ancillary image builds: hybrid** ✅
   - Pre-build and tag for common/stable steps (faster)
   - Build on-demand for custom/experimental steps (more flexible)
   - Implementation: check for pre-built tag first, fall back to build

6. **Session routing URL pattern: Option B (cookie/header)** ✅
   - Use session cookie or header, keep paths simple
   - More shareable URLs (can share `/terminal/` link directly)
   - Session identified by cookie set on session creation
   - Frontend sends session ID in header or cookie with each request

7. **Resource limits per namespace: start conservative** ✅
   - 2 CPU, 4Gi RAM per namespace (initial values)
   - No empirical data yet, adjust based on real usage
   - Monitor and tune after deployment

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
