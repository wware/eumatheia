"""FastAPI orchestrator application."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles

from .exhibit_loader import ExhibitLoader
from .namespace_manager import NamespaceManager
from .session_manager import SessionManager

# Global state
session_manager: SessionManager | None = None
exhibit_loader: ExhibitLoader | None = None
namespace_manager: NamespaceManager | None = None


async def reaper_task():
    """Background task to reap idle sessions."""
    while True:
        await asyncio.sleep(60)  # Check every minute
        if session_manager and namespace_manager:
            reaped = session_manager.reap_idle_sessions()
            if reaped:
                print(f"Reaped {len(reaped)} idle sessions: {reaped}")
                # Clean up Kubernetes namespaces for reaped sessions
                for session_id in reaped:
                    await namespace_manager.delete_namespace(session_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global session_manager, exhibit_loader, namespace_manager

    # Startup
    session_manager = SessionManager(idle_timeout_seconds=1800)  # 30 minutes
    exhibit_loader = ExhibitLoader(Path(__file__).parent.parent.parent / "exhibits")
    namespace_manager = NamespaceManager()

    # Start reaper task
    reaper = asyncio.create_task(reaper_task())

    yield

    # Shutdown
    reaper.cancel()
    try:
        await reaper
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Edutopia",
    description="Interactive software engineering learning platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static files - serve the built React frontend
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")


@app.get("/")
async def root():
    """Serve the frontend."""
    from fastapi.responses import FileResponse

    return FileResponse(frontend_dist / "index.html")


@app.post("/api/sessions")
async def create_session(request: Request, exhibit_id: str):
    """
    Create a new learning session.

    Args:
        exhibit_id: ID of the exhibit to start

    Returns:
        Session details including session_id and first step
    """
    # Load exhibit to verify it exists and get first step
    try:
        exhibit = exhibit_loader.load_exhibit(exhibit_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Exhibit not found: {exhibit_id}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not exhibit.first_step:
        raise HTTPException(status_code=400, detail="Exhibit has no steps")

    # Create session
    session = session_manager.create_session(exhibit_id, exhibit.first_step.id)

    # Provision Kubernetes namespace for this session
    try:
        namespace_metadata = await namespace_manager.create_namespace(session.session_id)
        print(f"Created namespace for session {session.session_id}: {namespace_metadata}")
    except Exception as e:  # noqa: BLE001 - intentionally catch all for namespace provisioning
        # Roll back session if namespace creation fails
        session_manager.delete_session(session.session_id)
        raise HTTPException(
            status_code=500, detail=f"Failed to provision namespace: {type(e).__name__}: {e!s}"
        )

    return {
        "session_id": session.session_id,
        "exhibit_id": session.exhibit_id,
        "current_step": session.current_step,
    }


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Update activity timestamp
    session_manager.update_activity(session_id)

    return {
        "session_id": session.session_id,
        "exhibit_id": session.exhibit_id,
        "current_step": session.current_step,
    }


@app.get("/api/sessions/{session_id}/step")
async def get_current_step(session_id: str):
    """Get details about the current step."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Load exhibit and find current step
    exhibit = exhibit_loader.load_exhibit(session.exhibit_id)
    step = exhibit.get_step(session.current_step)

    if not step:
        raise HTTPException(status_code=500, detail="Current step not found in exhibit")

    # Update activity
    session_manager.update_activity(session_id)

    # Load narrative content
    narrative_path = Path(__file__).parent.parent.parent / step.narrative
    try:
        narrative_content = narrative_path.read_text()
    except FileNotFoundError:
        narrative_content = f"*Narrative not found: {step.narrative}*"

    return {
        "step": step.model_dump(),
        "narrative_content": narrative_content,
        "has_next": step.next is not None,
    }


@app.post("/api/sessions/{session_id}/next")
async def advance_to_next_step(session_id: str):
    """Advance to the next step."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Load exhibit and find current step
    exhibit = exhibit_loader.load_exhibit(session.exhibit_id)
    current_step = exhibit.get_step(session.current_step)

    if not current_step:
        raise HTTPException(status_code=500, detail="Current step not found")

    if not current_step.next:
        raise HTTPException(status_code=400, detail="Already at final step")

    # Update session to next step
    session_manager.update_step(session_id, current_step.next)

    return {"current_step": current_step.next}


@app.put("/api/sessions/{session_id}/step")
async def set_current_step(session_id: str, request: Request):
    """Set the current step (for navigation backwards)."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Parse request body
    body = await request.json()
    step_id = body.get("step_id")

    if not step_id:
        raise HTTPException(status_code=400, detail="step_id required")

    # Verify step exists in exhibit
    exhibit = exhibit_loader.load_exhibit(session.exhibit_id)
    step = exhibit.get_step(step_id)

    if not step:
        raise HTTPException(status_code=400, detail=f"Invalid step_id: {step_id}")

    # Update session to specified step
    session_manager.update_step(session_id, step_id)

    return {"current_step": step_id}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and clean up resources."""
    deleted = session_manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    # Clean up Kubernetes namespace
    try:
        await namespace_manager.delete_namespace(session_id)
    except Exception as e:  # noqa: BLE001 - intentionally catch all for cleanup
        print(f"Warning: Failed to delete namespace for session {session_id}: {e}")

    return {"message": "Session deleted"}


@app.api_route("/app/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy_app(request: Request, path: str):
    """
    Proxy requests to the example app service.
    For now, proxies to a shared app. Later will route to per-session containers.
    """
    target_url = f"http://host.docker.internal:9000/{path}"

    if request.url.query:
        target_url += f"?{request.url.query}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
                content=await request.body(),
                timeout=30.0,
            )

            return Response(
                content=response.content,
                status_code=response.status_code,
                headers={
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() not in ["content-encoding", "content-length", "transfer-encoding"]
                },
            )
        except httpx.RequestError as e:
            import traceback

            traceback.print_exc()
            raise HTTPException(
                status_code=502, detail=f"Error connecting to app: {type(e).__name__}: {e!s}"
            )
        except Exception as e:  # noqa: BLE001 - intentionally catch all for proxy errors
            import traceback

            traceback.print_exc()
            raise HTTPException(
                status_code=500, detail=f"Unexpected error: {type(e).__name__}: {e!s}"
            )


@app.api_route("/terminal/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy_terminal(request: Request, path: str):
    """
    Proxy requests to the terminal service.
    For now, proxies to a shared terminal. Later will route to per-session containers.
    """
    # Construct target URL - proxy to host's localhost where terminal is exposed
    # For prototype, terminal is exposed on host port 7681
    target_url = f"http://host.docker.internal:7681/{path}"

    # Forward query parameters
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Create httpx client
    async with httpx.AsyncClient() as client:
        # Forward the request
        try:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
                content=await request.body(),
                timeout=30.0,
            )

            # Return the response
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers={
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() not in ["content-encoding", "content-length", "transfer-encoding"]
                },
            )
        except httpx.RequestError as e:
            import traceback

            traceback.print_exc()
            raise HTTPException(
                status_code=502, detail=f"Error connecting to terminal: {type(e).__name__}: {e!s}"
            )
        except Exception as e:  # noqa: BLE001 - intentionally catch all for proxy errors
            import traceback

            traceback.print_exc()
            raise HTTPException(
                status_code=500, detail=f"Unexpected error: {type(e).__name__}: {e!s}"
            )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
