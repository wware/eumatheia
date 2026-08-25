Good — confirms gotty's already swapped in on both Dockerfiles (7681), and `main.py`'s `/terminal/*` proxy just needs its target host, not a protocol change. And I can see the current frontend is a single vanilla-JS `index.html` with panes stacked and toggled via `display: none/block` — not tabbed, not React yet. So this is really a frontend rewrite, not a modification.

Here's a plan.

## Frontend Pane UI — Plan

**Layout model (your call, made concrete):** one content well, tabs across the top selecting what's in it — closer to Chrome tabs than VSCode's editor-group model (no split groups, no sidebar file tree to replicate). Each visible pane from the step's `panes` list becomes a tab; narrative becomes a tab too (first one, selected by default) rather than a permanently visible sidebar — keeps the "single window" idea honest instead of secretly being narrative+split after all. Flagging this as the one real assumption in the plan — easy to flip to a persistent narrative header if you'd rather not click away from the instructions to see the terminal.

**Component architecture (React, functional + hooks, no pane-layout library needed since there's no splitting anymore):**
- `App` — owns `session_id`, current step data, fetch/advance logic
- `TabBar` — renders tabs from `step.panes` (+ narrative), tracks `activeTab`
- `TabContent` — one wrapper per tab; **all tabs stay mounted**, only the active one is visible (`display` toggle, not conditional render/unmount)
- `NarrativePane` — markdown render + "Copy to Terminal" button on code fences
- `TerminalPane` — `<iframe>` onto the gotty URL for this session
- `IframePane` — generic, for the `path` on any `iframe`-type pane (dashboard, app UI, etc.)
- `StepNav` — Back / Next / manual-verify Continue button, reflecting `verify.type`

**Why mounted-not-unmounted matters:** the terminal is a websocket-backed iframe. Unmounting on tab-switch would kill the shell session and scrollback every time the learner glances at the narrative. This is the one non-obvious constraint the whole component tree has to respect — worth stating explicitly since it's easy for a "clean" React implementation to get this wrong by conditionally rendering the active pane.

**Data flow:** no backend contract changes needed — `GET /api/sessions/{id}/step` already returns `step.panes` with everything needed to build the tab list; `POST .../next` and `PUT .../step` already drive navigation. The React app is a pure consumer of the existing FastAPI JSON API plus raw iframe URLs for terminal/app.

**Build & serve:** 
- Vite for the React build (fast, minimal config, standard choice here).
- Dev: `vite dev` server proxying `/api/*` to the FastAPI orchestrator on 8000, so hot reload works without touching CORS.
- Prod/compose: `vite build` emits static assets; orchestrator's existing `StaticFiles` mount at `/static` (and the `FileResponse` on `/`) just needs to point at `dist/` instead of the current hand-written `index.html`. No new services — the orchestrator container gains a build step (or a separate build stage in `Dockerfile.orchestrator` via multi-stage build: `node` stage builds, `python` stage copies `dist/`).

**Migration order:**
1. Scaffold Vite + React app alongside (not replacing) current `static/index.html`, hitting the live FastAPI backend in dev mode — de-risks the API integration before touching layout.
2. Build `TabBar`/`TabContent` shell with static/dummy panes, get the "always-mounted, toggle visibility" behavior right and tested with the terminal specifically (that's the part most likely to regress).
3. Wire in `NarrativePane` markdown rendering + copy-to-terminal (needs an xterm-free approach now since gotty owns the terminal — copy-to-terminal has to go through gotty's own input mechanism or a synthetic paste into the iframe, which is worth a closer look since it's a cross-origin iframe boundary, same limitation the README already calls out for iframe panes in general).
4. Wire `StepNav` to the existing `next`/`step` endpoints.
5. Swap the orchestrator's static-serving target from `static/index.html` to the Vite `dist/`, retire the old prototype file.
6. Docker/compose: multi-stage build for the orchestrator image, or a separate frontend-build container if you'd rather keep the orchestrator image Python-only.

**Open decisions before coding starts:**
- Narrative-as-tab vs. persistent header (flagged above).
- Copy-to-terminal mechanism now that the terminal is an iframed gotty instance rather than an in-page `xterm.js` — this is the one place the README's original plan ("direct JS call into the xterm.js instance") no longer applies cleanly and needs a real answer before that step gets built.
- Whether tab order/set is purely derived from `step.panes` each time (tabs can appear/disappear step to step) or whether some tabs (e.g. narrative) should persist across the whole exhibit regardless of what a given step lists.

---

> one tweak - the narrative (the main markdown thing) shouldn't be one of the tabs, it should always be up, either on the side or the top (maybe buttons to move it to the viewer's preference?) I think this addresses a concern you expressed about killing processes

---

Good, that resolves the assumption I flagged, and yes — it sidesteps the mounted-tab question entirely for the narrative specifically (it was never at risk of losing state, but keeping it out of the tab rotation means the learner never loses sight of the instructions while poking at a terminal, which is arguably the more important property).

Updated layout:

**Layout model:** persistent narrative pane + a tabbed content well for everything else (terminal, iframes). Narrative position is user-configurable — side or top — via a toggle in the header, not baked into the exhibit content itself (it's a viewing preference, not something an exhibit author should have to think about per-step).

**Component changes from the previous plan:**
- `NarrativePane` is no longer a tab — it moves up to live alongside `TabBar`/`TabContent` as a sibling, not inside it.
- New `LayoutShell` component owns the side/top arrangement: a simple CSS flex-direction toggle (`row` for side, `column` for top) driven by a piece of UI state (`narrativePosition: 'side' | 'top'`).
- `TabBar`/`TabContent` now only ever reflect the *non-narrative* panes from `step.panes` — so the mounted-not-unmounted rule I called out still applies, but only to terminal/iframe tabs, which is exactly the set that actually needed it.
- The narrative-position toggle is a pure client-side preference — reasonable to keep in a bit of local component state to start, and worth promoting to `localStorage` once persistence-across-reloads matters (not needed for a first pass).

**Where this lands in the migration order:** it slots into step 2 (the `TabBar`/`TabContent` shell) — build `LayoutShell` at the same time, since it's what everything else nests inside, rather than retrofitting it after tabs exist.

One thing this reopens rather than closes: with narrative always visible, "Copy to Terminal" now needs to copy *into* a tab that might not be the active one — so the button either (a) also switches the active tab to the terminal, or (b) writes to the terminal in the background without switching. Worth deciding alongside the copy-to-terminal mechanism itself in step 3, since both questions are really about how much the narrative pane is allowed to reach into the tab well.

---

> Regarding the "copy to terminal" question, I think whatever you hit the button for, it should be copied to the currently active pane. It is the user's responsibility to choose the right pane before hitting the Copy button.