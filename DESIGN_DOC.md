# Eumatheia — Interactive Software Engineering Learning Platform

**Design Doc v2** — supersedes `README.md` and `NEXT_STEPS.md`.

**Status:** Active development. Sections are marked **[BUILT]**, **[PROTOTYPE]**, or **[PLANNED]** so this doc stays honest about what exists versus what's designed but not yet real. Nothing here should be taken as "done" unless it says `[BUILT]`.

**Why this doc exists:** the original `README.md` spec and the `NEXT_STEPS.md` running conversation log had diverged — README describes Kubernetes-namespace isolation; the code that actually got built (`container_manager.py`) is a Docker-per-session prototype that doesn't match it. This doc resolves that: **Kubernetes namespaces are the target architecture.** The Docker container-manager code is prototype scaffolding, written to unblock frontend/content-model work without standing up a cluster, and will be replaced rather than extended. Where the two disagree below, Kubernetes wins.

---

## 1. Goal

A general-purpose, browser-based platform for hands-on software engineering tutorials: the learner reads narrative, runs real commands against a real (if small, disposable) backend environment, and sees results reflected in real tools — without installing anything locally.

Mental model: **a Jupyter notebook on steroids.** Like a notebook, it interleaves explanation with live, executable content and keeps state as you move through it. Unlike a notebook, each step can drive a real terminal, a real disposable backend environment, and real external tools/dashboards relevant to the topic, all visible at once in separate panes.

Not a video course, not copy-paste snippets run blind — the point is a real, live, disposable environment per learner, driven by a content format general enough to cover more than one domain.

**Candidate use cases** (illustrative, not exhaustive — chosen specifically to keep the content model domain-agnostic):
- **Kubernetes fundamentals** (existing k8s-hack content) — terminal running `kubectl`, an iframe showing a dashboard, verify steps checking pod state.
- **Graphwright** (typed knowledge graph platform) — terminal running Python against the Graphwright library/MCP server, possibly an iframe onto graph-viz output, verify steps checking query results rather than pod state.

Nothing in the content model (Section 5) should be Kubernetes-specific, even though Kubernetes is the isolation substrate — a Graphwright track's namespace holds a plain Python container and nothing k8s-flavored beyond the isolation boundary itself.

---

## 2. Target Architecture — Kubernetes namespace per session

```
                     ┌────────────────────────────────┐
Browser  ───────────▶│   Orchestrator (Python)        │
(single page,        │   - session lifecycle          │
 multi-pane UI)      │   - YAML step loader           │
                     │   - reverse proxy / routing    │
                     └──────────────┬─────────────────┘
                                    │
                     ┌──────────────▼─────────────────┐
                     │  Shared kind/minikube cluster  │
                     │  (one VM, DigitalOcean/AWS)    │
                     │                                │
                     │  namespace: sess-abc123        │
                     │    - terminal server (gotty)   │
                     │    - track-specific workload   │
                     │    - ResourceQuota/LimitRange  │
                     │    - NetworkPolicy (isolate)   │
                     │                                │
                     │  namespace: sess-def456        │
                     │    - ...                       │
                     └────────────────────────────────┘
```

One VM, one Kubernetes cluster (kind or minikube), many namespaces — one per learner session. The namespace is a generic, cheap sandboxing primitive; it's used as such whether or not the *content* of a given track is about Kubernetes. A k8s track's namespace holds real k8s workloads (pods, deployments); a Graphwright track's namespace holds a container running a Python/Graphwright environment and nothing else k8s-specific. The namespace *is* the unit of isolation, resource capping, and cleanup regardless of what's running inside it.

**[PLANNED]** — nothing in the current codebase talks to a Kubernetes API yet.

---

## 3. Session Model **[PARTIALLY BUILT]**

- **Session ID** doubles as the Kubernetes namespace name. Generated server-side on first visit as `sess-` + 8 hex chars (`SessionManager._generate_session_id`, **[BUILT]** — uses `secrets.token_hex(4)`, well under the 63-char namespace limit).
- **No auth for this phase.** Anyone can start a session; abuse containment happens entirely at the namespace level (quotas, network policy, idle reaping), not at the account level. **[PLANNED]** — no quota/network-policy enforcement exists yet since nothing talks to Kubernetes.
- **Idle reaping. [BUILT]** `SessionManager.reap_idle_sessions()` + a 60-second-interval background task in `main.py` already tear down sessions after 30 minutes of inactivity (`idle_timeout_seconds=1800`). Currently this only deletes the in-memory `Session` record and calls the (stub) `ContainerManager.destroy_container` — it needs to call namespace teardown once Kubernetes provisioning exists.
- **Restore URL (optional, opt-in).** On request, persist `{restore_token → exhibit_id, current_step}` to a small local store (SQLite is sufficient). Visiting a restore URL re-provisions a fresh namespace for that exhibit and jumps to the stored step — a *rewind to where you were*, not a snapshot of mutated state; no PV backups, no etcd snapshotting. Worth surfacing that distinction in the UI copy. **[PLANNED]** — not implemented; sessions currently only live in an in-memory dict (`SessionManager._sessions`), so they don't survive an orchestrator restart at all yet, restore token or not.

**Session model implementation note:** `Session` is a frozen Pydantic model (matches your stated preference); `SessionManager` mutates by `model_copy(update=...)` rather than in-place field assignment. Keep that pattern for whatever `NamespaceMetadata`/`ContainerMetadata`-equivalent model replaces the current `ContainerManager` bookkeeping.

---

## 4. Per-Session Resource Isolation **[PLANNED]**

Each namespace gets, at creation time:
- `ResourceQuota` — caps total CPU/memory requests and limits for the namespace. Primary defense against runaway or malicious workloads (e.g. cryptomining), given there's no auth to fall back on.
- `LimitRange` — default per-pod/container CPU and memory limits, so one pod can't silently consume the whole namespace quota.
- `NetworkPolicy` — default-deny cross-namespace traffic, so session A cannot reach session B's pods/services. Egress can be restricted too if outbound abuse becomes a concern.
- A scoped `ServiceAccount` + `Role`/`RoleBinding`, limited to that namespace — the learner's terminal should never be able to `kubectl` outside their own namespace.

This is deliberately the *whole* security model for this phase: no account system, no billing, just hard per-namespace resource and network fences plus a TTL.

None of this exists yet. This is the section that most directly motivates ditching the Docker-container prototype: Docker alone doesn't give you an equivalent to `NetworkPolicy` or namespace-scoped RBAC without reinventing a chunk of Kubernetes by hand.

---

## 5. Content Model (YAML) **[BUILT, ahead of the README's original spec]**

Exhibits are directory-based (this was a `NEXT_STEPS.md` proposal and it shipped):

```
exhibits/
  demo/
    exhibit.yaml
    Dockerfile.example
  docker-demo/
    exhibit.yaml
    Dockerfile.app
    docker-compose.app.yml
    setup.sh
  fastapi-crud/
    exhibit.yaml
```

Narratives currently live centrally in `narratives/` at the project root rather than per-exhibit — that was flagged as an open decision in `NEXT_STEPS.md` ("keep centralized for now, easier to share across exhibits") and the code reflects that choice: `Step.narrative` paths resolve from the project root, not the exhibit directory.

Actual schema, from `src/eumatheia/models.py` (this **is** the schema, not aspirational):

```yaml
exhibit: self-healing
title: "Self-Healing Deployments"
setup:
  - manifest: manifests/toy-api-deployment.yaml   # applied to the namespace at session start
steps:
  - id: delete-pod
    narrative: narratives/delete-pod.md
    panes:
      - type: terminal
        label: "Shell"
      - type: iframe
        label: "Dashboard"
        path: "/dashboard/"
    ancillary:                        # [BUILT] — per-step provisioning inputs
      dockerfile: Dockerfile.intro    # relative to the exhibit directory
      compose: docker-compose.intro.yml
      scripts:
        - setup.sh
    verify:
      type: shell
      command: "kubectl get pods -l app=toy-api -o jsonpath='{.items[*].status.phase}'"
      expect_contains: "Running"
    next: scale-deployment

  - id: choose-your-path
    narrative: narratives/choose-path.md
    panes: [...]
    nav:                              # [BUILT] — overrides default Next/Back buttons
      - label: "Learn Docker"
        target: docker-intro
      - label: "Learn Kubernetes"
        target: k8s-intro
      - label: "Back"
        target: previous
    verify:
      type: manual
    next: null
```

Field notes:
- `setup` — manifests applied to the namespace when the exhibit starts (idempotent; re-run on restore). **[PLANNED]** — `SetupManifest.manifest` exists in the Pydantic model but nothing consumes it yet; once Kubernetes provisioning lands, this is where "apply these manifests to the fresh namespace" happens.
- `panes` — terminal, iframe, or markdown for a given step.
- `ancillary` — **[BUILT]** Dockerfile/compose/script references, validated at load time (`ExhibitLoader._validate_ancillary_files` raises `FileNotFoundError` if a referenced file is missing). This was designed for the Docker-prototype's per-session provisioning; it's still the right shape for Kubernetes — `dockerfile`/`compose` become "build this image, use it as the pod's container spec" instead of "run this via docker-compose."
- `verify` — `shell` (scripted, pass/fail on output match) or `manual` (a Continue button, for anything needing human judgment). **[BUILT]** as a Pydantic discriminated union; **[PLANNED]** — nothing actually executes `verify: shell` commands yet, `main.py` has no endpoint for it.
- `nav` — **[BUILT]** in the model; **[PLANNED]** in the frontend — `StepNav.tsx` doesn't yet branch on `nav` being present, it still assumes linear Back/Next.
- `next` — explicit pointer to the next step ID, not array order, so branching can be added without a schema rewrite.

---

## 6. Frontend — Multi-Pane Browser UI **[BUILT]**

This shipped and it's a real rewrite from the original vanilla-JS `static/index.html` prototype (which still exists in the repo but is dead — nothing serves it; `main.py` now serves `frontend/dist/`).

**Layout model:** persistent narrative pane + a tabbed content well for everything else (terminal, iframes). This is *not* what the README originally specified (which had narrative as just another tab) — it was revised mid-build specifically to guarantee the terminal's websocket connection is never torn down by a tab switch, and to keep instructions visible while the learner works in a terminal. Narrative position (side vs. top) is a client-side viewing preference via `LayoutShell`, not something baked into exhibit content.

**Components** (`frontend/src/components/`):
- `App.tsx` — owns `session_id`, current step data, fetch/advance logic.
- `LayoutShell` — owns the side/top arrangement (flex-direction toggle).
- `TabBar` / `TabContent` — render tabs from the step's non-narrative `panes`; **all tabs stay mounted**, only the active one is visibility-toggled (never conditionally rendered/unmounted) — this is the load-bearing constraint that keeps the terminal's websocket alive across tab switches.
- `NarrativePane` — markdown render + "Copy to Terminal" button on code fences. Copies into whichever pane is currently active (your call: "it is the user's responsibility to choose the right pane before hitting Copy").
- `TerminalPane` — `<iframe>` onto the terminal server's URL for this session (not `xterm.js` in-page, see Section 7).
- `IframePane` — generic, for any `iframe`-type pane (dashboard, app UI, etc.).
- `StepNav` — Back / Next / manual-verify Continue, reflecting `verify.type`. Doesn't yet branch on `nav` (see Section 5).

**Build & serve [BUILT]:** Vite for the React build. Dev: `vite dev` proxies `/api/*` to FastAPI on 8000. Prod: `Dockerfile.orchestrator` is a multi-stage build — a `node:20-slim` stage runs `npm run build`, a `python:3.13-slim` stage copies `dist/` in and serves it via `StaticFiles`/`FileResponse` from `main.py`.

**Known gap:** iframe panes are subject to the standard cross-origin scripting boundary — content *inside* a cross-origin iframe can't be reached from the parent page. Copy-to-terminal only works because the terminal target is also reached through an iframe whose input mechanism (gotty's own websocket) is the copy target, not direct DOM/JS access into it.

---

## 7. Terminal Server — gotty **[DECIDED, PARTIALLY BUILT]**

Decision already made in `NEXT_STEPS.md` and reflected in the frontend rewrite: the terminal is `gotty` running in-container, embedded via `<iframe>`, **not** `xterm.js` connected directly to a PTY in-page as the original README draft assumed. That assumption is why "Copy to Terminal" couldn't stay a direct JS call into an `xterm.js` instance — it now has to go through gotty's own input mechanism inside the iframe.

**Cleanup needed:** the repo currently has three terminal-server Dockerfiles — `Dockerfile.gotty`, `Dockerfile.ttyd`, `Dockerfile.ttyd-source` — left over from evaluating gotty vs. ttyd (binary vs. built-from-source). Only `Dockerfile.example-app` (which bundles gotty directly alongside the demo app) is actually referenced by `docker-compose.yml`. The other two are dead weight from the exploration phase — either delete them or, if ttyd is still worth keeping as a documented alternative, say so explicitly; right now they just add to the "too much stuff to keep straight" problem this doc is meant to fix.

---

## 8. Orchestrator (Python/FastAPI) **[PARTIALLY BUILT]**

Actual endpoints in `src/eumatheia/main.py` today:

| Endpoint | Status | Notes |
|---|---|---|
| `POST /api/sessions?exhibit_id=` | **[BUILT]** | Creates session, calls `ContainerManager.provision_container` (stub — see Section 9) |
| `GET /api/sessions/{id}` | **[BUILT]** | |
| `GET /api/sessions/{id}/step` | **[BUILT]** | Returns step config + rendered narrative markdown |
| `POST /api/sessions/{id}/next` | **[BUILT]** | Linear advance only |
| `PUT /api/sessions/{id}/step` | **[BUILT]** | Arbitrary step_id — already supports what non-linear `nav` needs server-side |
| `DELETE /api/sessions/{id}` | **[BUILT]** | |
| `/app/{path}` proxy | **[PROTOTYPE]** | Hardcoded to `host.docker.internal:9000` — one shared app for every session, explicitly not per-session yet |
| `/terminal/{path}` proxy | **[PROTOTYPE]** | Hardcoded to `host.docker.internal:7681` — one shared terminal for every session |
| `verify: shell` execution | **[PLANNED]** | No endpoint exists |

Responsibilities not yet built at all: session lifecycle tied to real namespace creation, applying `setup` manifests via the Kubernetes Python client, routing `/sess-<id>/terminal` and `/sess-<id>/<service>/` to the correct in-namespace service instead of one hardcoded host port for everybody.

**Minor hygiene note:** `main.py` sets the FastAPI app title to `"Edutopia"`, while the package, directory, and everything else is `eumatheia`. Worth reconciling — pick one name and use it everywhere (title, `pyproject.toml` description, this doc).

---

## 9. Current Implementation Status — honest inventory

**Real and working today, as a single-shared-container dev harness (not session-isolated):**
- Directory-based exhibits + ancillary file validation.
- Session CRUD + step navigation API.
- Idle reaping (in-memory only).
- Full React frontend (persistent narrative, tabbed terminal/iframe panes, gotty-in-iframe terminal, copy-to-terminal).
- One shared `example-app` container (`Dockerfile.example-app`) running both the demo FastAPI CRUD app (port 8080) and gotty (port 7681), proxied by the orchestrator. Every session currently gets the *same* container — there is no isolation between learners yet.

**Explicitly prototype scaffolding, to be replaced (not extended):**
- `container_manager.py` — allocates sequential port numbers and stores metadata in a dict; `provision_container`/`destroy_container` are both stubs with `# TODO: Implement...` comments. This whole module gets replaced by a Kubernetes-namespace provisioner (Section 10).
- `docker-compose.yml` — a two-service dev-mode compose file (orchestrator + example-app), useful for local frontend/API development, not a deployment target.

**Dead / leftover:**
- `static/index.html` — the original vanilla-JS prototype UI, superseded by the React frontend, no longer served.
- `Dockerfile.ttyd`, `Dockerfile.ttyd-source` — superseded by the gotty decision (Section 7).
- `SetupManifest` model field exists but nothing reads it yet.

---

## 10. Migration Plan — Docker prototype → Kubernetes target

Rough order, each step should leave things working:

1. **Stand up the cluster.** Get `kind` or `minikube` running on the target VM; confirm the Kubernetes Python client (`kubernetes` package — not currently a dependency, needs adding to `pyproject.toml`) can talk to it from the orchestrator process.
2. **Write the namespace provisioner.** New module (replaces `container_manager.py`): `create_namespace(session_id) -> None`, applying `ResourceQuota`, `LimitRange`, `NetworkPolicy`, `ServiceAccount`/`Role`/`RoleBinding` at creation. Mirror the frozen-model pattern from `SessionManager` for whatever metadata needs tracking.
3. **Apply `setup` manifests.** Consume `Exhibit.setup` (already modeled, unused) to apply track-specific manifests into the fresh namespace.
4. **Per-session terminal pod.** Replace the shared gotty container with a gotty pod per namespace, scoped to that namespace's ServiceAccount.
5. **Real reverse proxy routing.** Replace the hardcoded `host.docker.internal:9000`/`:7681` targets in `proxy_app`/`proxy_terminal` with per-session lookups (`/sess-<id>/terminal`, `/sess-<id>/<service>/`) resolved against the namespace's in-cluster service.
6. **Wire teardown.** Point `reap_idle_sessions()` and `DELETE /api/sessions/{id}` at real namespace deletion instead of the stub `destroy_container`.
7. **`verify: shell` execution.** `kubectl exec` into an existing pod (simpler) vs. a short-lived `Job` (more isolated from whatever state the learner left the pod in) — open question, see Section 12.
8. **Non-linear nav in the frontend.** `StepNav.tsx` branches on `Step.nav` when present, renders custom buttons instead of Back/Next.
9. **Delete the dead weight.** `static/index.html`, `Dockerfile.ttyd*`, the old `container_manager.py`.

---

## 11. Deployment Target

Single "comfortably large" VM (DigitalOcean Droplet or AWS EC2), running:
- kind or minikube as the shared cluster
- The Python orchestrator (FastAPI)
- A reverse proxy (nginx or the orchestrator itself) handling WebSocket upgrade for terminals and routing for iframes

---

## 12. Explicitly Deferred (not solved by this doc)

- **Tracks whose external tools don't fit cleanly in one namespace** — some heavier tools (a shared control plane, a service with its own multi-tenancy model) won't fit the "everything lives in the learner's namespace" assumption. Not a problem for k8s-hack or Graphwright; revisit if/when a track needs one.
- **Horizontal scale beyond one VM** — one shared cluster has a ceiling; sharding sessions across multiple VMs/clusters is a later problem.
- **VM-level failure** — a restart of the shared VM currently takes down every active session at once.
- **Auth, billing, paid tier (real EKS access)** — this spec is free-tier-only; a paid tier's isolation and cost-control model (per-session real clusters, metered billing) is a separate design effort.
- **Restore-across-orchestrator-restart** — sessions are in-memory only right now; SQLite-backed restore tokens are designed (Section 3) but not built.

---

## 13. Open Questions

1. Exact idle-timeout value and what counts as "activity" (HTTP hit vs. terminal keystroke vs. both) — currently just HTTP hits, 30 min.
2. `verify: shell` — `kubectl exec` into an existing pod vs. a short-lived `Job`.
3. Narratives: stay centralized at project root, or move per-exhibit now that ancillary files already live per-exhibit? (Originally leaned centralized "for now" — worth revisiting since the directory-based refactor already happened for everything else.)
4. `Dockerfile.ttyd` / `Dockerfile.ttyd-source` — delete, or keep as a documented fallback if gotty turns out to have some limitation under real per-namespace routing?
5. App/package naming: `eumatheia` vs. `Edutopia` (FastAPI title) — pick one.