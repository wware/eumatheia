# Eumatheia React Frontend

Modern React + TypeScript frontend for the Eumatheia interactive learning platform.

## Development

```bash
# Install dependencies
npm install

# Start dev server (proxies /api to localhost:8000)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Architecture

- **React** - Component-based UI
- **TypeScript** - Type safety
- **Vite** - Fast build tool with HMR
- **API Proxy** - Development server proxies `/api/*` to FastAPI orchestrator on port 8000

## Current Status

✅ **Step 1 Complete**: Vite + React + TypeScript scaffolded
- Basic app structure created
- API proxy configured
- Session creation tested and working

🔨 **Next Steps** (from NEXT_STEPS.md):
1. Build LayoutShell component (persistent narrative + tabbed content)
2. Build TabBar/TabContent shell (always-mounted tabs)
3. Wire NarrativePane (markdown rendering + copy-to-terminal)
4. Wire StepNav (back/forward navigation)
5. Swap orchestrator to serve React dist
6. Add Docker multi-stage build

## Key Design Decisions

- **Persistent Narrative**: Always visible, configurable position (side or top)
- **Mounted Tabs**: Terminal/iframe tabs stay mounted to preserve state (critical for WebSocket-backed gotty terminal)
- **Pure Consumer**: React app consumes existing FastAPI JSON API without backend changes
