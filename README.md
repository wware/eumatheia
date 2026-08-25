# Interactive Software Engineering Learning Platform — Design Spec

**Status:** Proposal / pre-implementation

**Scope:** Free tier only. No auth. Single server. Namespace-per-session isolation. Limitations of the single-cluster model are acknowledged and explicitly deferred.

## 1. Goal

A general-purpose, browser-based platform for hands-on software engineering tutorials: the learner reads narrative, runs real commands against a real (if small, disposable) backend environment, and sees the results reflected in real tools — without installing anything locally.

The working mental model is a **Jupyter notebook on steroids**: like a notebook, it interleaves explanation with live, executable content and keeps state as you move through it — but instead of being limited to inline code cells and their output, each step can drive a real terminal, a real disposable backend environment, and real external tools/dashboards relevant to the topic, all visible at once in separate panes.

Not a video course, not a static tutorial with copy-paste snippets the learner runs blind — the point is a real, live, disposable environment per learner, driven by a content format general enough to cover more than one domain.

**Candidate use cases** (not the platform's whole purpose — illustrations of the range it needs to cover):

- **Kubernetes fundamentals** (existing k8s-hack content) — terminal running `kubectl`, an iframe showing a dashboard, verify steps checking pod state.
- **Graphwright** (typed knowledge graph platform) — terminal running Python against the Graphwright library/MCP server, possibly an iframe onto graph-viz output, verify steps checking query results or graph state rather than pod state.

The point of naming two dissimilar use cases up front is to keep the content model (Section 5) domain-agnostic — nothing in the step schema should be k8s-specific.

## 2. High-level architecture

```
                     ┌───────────────────────────────┐
Browser  ───────────▶│   Orchestrator (Python)       │
(single page,        │   - session lifecycle         │
 multi-pane UI)      │   - YAML step loader          │
                     │   - reverse proxy / routing   │
                     └──────────────┬────────────────┘
                                    │
                     ┌──────────────▼────────────────┐
                     │  Shared kind/minikube cluster │
                     │  (one VM, DigitalOcean/AWS)   │
                     │                               │
                     │  namespace: sess-abc123       │
                     │    - ttyd (terminal)          │
                     │    - track-specific workload  │
                     │    - ResourceQuota/LimitRange │
                     │    - NetworkPolicy (isolate)  │
                     │                               │
                     │  namespace: sess-def456       │
                     │    - ...                      │
                     └───────────────────────────────┘
```

One VM, one Kubernetes cluster (kind or minikube), many namespaces — one per learner session. The namespace is used here as a generic, cheap sandboxing primitive, not because the content is necessarily about Kubernetes itself: a Kubernetes track's namespace holds actual k8s workloads (pods, deployments); a Graphwright track's namespace holds a container running a Python/Graphwright environment and nothing k8s-specific beyond the isolation boundary. The namespace *is* the unit of isolation, resource capping, and cleanup regardless of what's running inside it.

## 3. Session model

- **Session ID** doubles as the Kubernetes namespace name. Generated server-side on first visit (e.g. `sess-` + 8 hex chars — short enough to satisfy the 63-character namespace name limit with room to spare), returned to the browser as a cookie.
- **No auth for this phase.** Anyone can start a session; abuse containment is handled entirely at the namespace level (quotas, network policy, idle reaping), not at the account level.
- **Idle reaping.** Orchestrator tracks last-activity time per session (last HTTP hit or terminal input) and tears down the namespace + associated pods after N minutes idle. This is the main cost/resource control given there's no auth to rate-limit by account.
- **Restore URL (optional, opt-in).** On request, the orchestrator persists `{restore_token → exhibit_id, current_step}` to a small local store (SQLite is sufficient). Visiting a restore URL re-provisions a fresh namespace for that exhibit and jumps straight to the stored step. This is a *rewind to where you were*, not a snapshot of mutated state — no PV backups, no etcd snapshotting. Worth surfacing that distinction to the learner in the UI copy.

## 4. Per-session resource isolation

Each namespace gets, at creation time:

- `ResourceQuota` — caps total CPU/memory requests and limits for the namespace (this is the primary defense against runaway or malicious workloads, e.g. cryptomining, given there's no auth to fall back on).
- `LimitRange` — default per-pod/container CPU and memory limits, so a single pod can't silently consume the whole namespace quota.
- `NetworkPolicy` — default-deny cross-namespace traffic, so session A cannot reach session B's pods or services. Egress can also be restricted here if outbound abuse becomes a concern.
- A scoped `ServiceAccount` + `Role`/`RoleBinding`, limited to that namespace — the learner's terminal should never be able to `kubectl` outside their own namespace.

This is deliberately the whole security model for this phase: no account system, no billing, just hard per-namespace resource and network fences plus a TTL.

## 5. Content model (YAML)

Each "exhibit" (using the term loosely — this phase is linear, not free-roaming) is a YAML file describing an ordered sequence of steps:

```yaml
exhibit: self-healing
title: "Self-Healing Deployments"
setup:
  - manifest: manifests/toy-api-deployment.yaml
  - manifest: manifests/toy-api-service.yaml
steps:
  - id: delete-pod
    narrative: narratives/delete-pod.md
    panes:
      - type: terminal
        label: "Shell"
      - type: iframe
        label: "Dashboard"
        path: "/dashboard/"   # e.g. a k8s dashboard, a Graphwright graph-viz view, etc.
    verify:
      type: shell
      command: "kubectl get pods -l app=toy-api -o jsonpath='{.items[*].status.phase}'"
      expect_contains: "Running"
    next: scale-deployment

  - id: scale-deployment
    narrative: narratives/scale-deployment.md
    panes:
      - type: terminal
        label: "Shell"
    verify:
      type: manual   # "does your output look right?" — no scripted check
    next: null        # end of exhibit
```

- `setup` — manifests applied to the namespace when the exhibit starts (idempotent; re-run on restore).
- `narrative` — path to a markdown file rendered in the markdown pane.
- `panes` — which panes are visible for this step (terminal, iframe, markdown always present).
- `verify` — either a scripted check (`shell` — a command run in-namespace, pass/fail on output match) or `manual` (a "Continue" button, for anything requiring human judgment, e.g. "look at the dashboard and confirm the diff").
- `next` — explicit pointer to the following step ID. Deliberately explicit rather than array-order, so branching can be added later without a schema rewrite.

The orchestrator reads this YAML, materializes the `setup` manifests into the session's namespace, and drives the frontend pane content step by step.

## 6. Frontend: multi-pane browser UI

A single-page app, not an embedded IDE. Tabs across the top, resizable/draggable panes underneath, built on a pane-layout library (e.g. `golden-layout`, `react-mosaic`, or `rc-dock`).

**Pane types:**

- **Markdown pane** — renders the current step's narrative. Code fences get a "Copy to Terminal" button that writes the command directly into the active terminal pane's input stream.
- **Terminal pane** — `xterm.js` in the browser, connected over WebSocket to a real PTY in the session's namespace. Simplest implementation: `ttyd` running as a sidecar/pod per session, wrapping a shell scoped to that namespace's service account. (Alternative if it's preferable to keep the terminal server in the same codebase as the orchestrator: a small Python WebSocket server using the `pty` module — more code, but one language throughout.)
- **iframe pane** — embeds an in-namespace web UI relevant to the track (a k8s dashboard, a Graphwright graph-viz view, a metrics dashboard, etc.), reverse-proxied through the orchestrator so it's reachable at a path like `/sess-abc123/<service>/`.

**Copy/paste between panes:** since everything lives in one page (not sandboxed VS Code webviews), a "Copy to Terminal" button is just a direct JS call into the xterm.js instance — no extension mechanism needed. The one hard limit: content *inside* a cross-origin iframe (ArgoCD, Prometheus) can't be scripted into or out of from the parent page — that's a browser security boundary, not something this architecture can route around. Copy-to-terminal works everywhere except iframe panes.

## 7. Orchestrator responsibilities (Python)

- Session lifecycle: create namespace + quota + network policy + terminal pod on first visit; idle-reap on timeout; handle restore-token lookups.
- YAML loading and step-state tracking per session (which step is the learner currently on).
- Applying `setup` manifests to the session's namespace (via the Kubernetes Python client).
- Reverse proxy: routes `/sess-<id>/terminal` (WebSocket) and `/sess-<id>/<service>/` (iframe targets) to the right in-namespace service.
- Running `verify` checks (`kubectl exec` or a short-lived `Job` in-namespace) and reporting pass/fail to the frontend.
- Serving the frontend's step-transition requests: on "Next," look up the next step in the YAML, update session state, return the new pane configuration.

## 8. Deployment target

Single "comfortably large" VM (DigitalOcean Droplet or AWS EC2), running:

- kind or minikube as the shared cluster
- The Python orchestrator (likely FastAPI, given existing stack preferences)
- A reverse proxy (nginx or the orchestrator itself) in front of everything, handling WebSocket upgrade for terminals and routing for iframes

## 9. Explicitly deferred (not solved by this spec)

- **Tracks whose external tools don't fit cleanly in one namespace.** Some heavier tools (a shared control plane, a service with its own multi-tenancy model) won't fit the "everything lives in the learner's namespace" assumption. Not a problem for the current use cases (k8s-hack, Graphwright); revisit if/when a track needs one.
- **Horizontal scale beyond one VM.** One shared cluster has a ceiling; sharding sessions across multiple VMs/clusters is a later problem.
- **VM-level failure.** A restart of the shared VM currently takes down every active session at once.
- **Auth, billing, paid tier (real EKS access).** This spec is free-tier-only; the paid tier's isolation and cost-control model (per-session real clusters, metered billing) is a separate design effort.
- **Non-linear / free-roaming navigation.** This spec assumes a strictly linear step sequence per exhibit.

## 10. Open questions before implementation

1. Terminal server choice: `ttyd` sidecar vs. custom Python `pty`-based WebSocket server.
2. Exact idle-timeout value and how "activity" is defined (HTTP hit vs. terminal keystroke vs. both).
3. Pane-layout library choice (golden-layout / react-mosaic / rc-dock) — depends on whether the frontend is React or vanilla JS.
4. Whether `verify: shell` checks run via `kubectl exec` into an existing pod or as a short-lived `Job` — exec is simpler, Job is more isolated from whatever state the learner has left the pod in.
