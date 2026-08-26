"""Manage per-session Docker containers."""

import subprocess
from pathlib import Path
from typing import Any


class ContainerManager:
    """Manages Docker containers for learning sessions."""

    def __init__(self, base_port: int = 10000):
        """
        Initialize container manager.

        Args:
            base_port: Starting port number for dynamic port allocation
        """
        self._base_port = base_port
        self._session_containers: dict[str, dict[str, Any]] = {}
        self._next_port_offset = 0

    def provision_container(
        self,
        session_id: str,
        exhibit_id: str,
        step_id: str,
        exhibit_dir: Path,
        dockerfile: str | None = None,
        compose_file: str | None = None,
    ) -> dict[str, Any]:
        """
        Provision a Docker container for a session.

        Args:
            session_id: Unique session identifier
            exhibit_id: Exhibit being run
            step_id: Current step ID
            exhibit_dir: Base directory for the exhibit
            dockerfile: Optional path to Dockerfile relative to exhibit_dir
            compose_file: Optional path to docker-compose.yml relative to exhibit_dir

        Returns:
            Dictionary with container metadata:
                - container_id: Docker container ID
                - ports: Dict mapping service names to ports
                - terminal_port: Port for terminal access
                - app_port: Port for application access (if applicable)
        """
        # Allocate ports for this session
        terminal_port = self._base_port + self._next_port_offset
        app_port = self._base_port + self._next_port_offset + 1
        self._next_port_offset += 2

        # For now, use the existing shared containers
        # TODO: Implement per-session container provisioning with docker-compose
        # This will involve:
        # 1. Generating a session-specific docker-compose.yml from the exhibit's compose file
        # 2. Substituting session-specific ports
        # 3. Running docker-compose up with a unique project name
        # 4. Tracking container IDs and ports

        metadata = {
            "session_id": session_id,
            "exhibit_id": exhibit_id,
            "step_id": step_id,
            "container_id": None,  # TODO: actual container ID
            "ports": {
                "terminal": terminal_port,
                "app": app_port,
            },
            "terminal_port": terminal_port,
            "app_port": app_port,
        }

        self._session_containers[session_id] = metadata
        return metadata

    def destroy_container(self, session_id: str) -> bool:
        """
        Destroy the Docker container for a session.

        Args:
            session_id: Session identifier

        Returns:
            True if container was destroyed, False if not found
        """
        if session_id not in self._session_containers:
            return False

        metadata = self._session_containers[session_id]

        # TODO: Implement actual container destruction
        # This will involve:
        # 1. Running docker-compose down with the session's project name
        # 2. Cleaning up any session-specific files

        del self._session_containers[session_id]
        return True

    def get_container_metadata(self, session_id: str) -> dict[str, Any] | None:
        """
        Get container metadata for a session.

        Args:
            session_id: Session identifier

        Returns:
            Container metadata dict, or None if not found
        """
        return self._session_containers.get(session_id)

    def get_terminal_port(self, session_id: str) -> int | None:
        """Get the terminal port for a session."""
        metadata = self.get_container_metadata(session_id)
        return metadata["terminal_port"] if metadata else None

    def get_app_port(self, session_id: str) -> int | None:
        """Get the app port for a session."""
        metadata = self.get_container_metadata(session_id)
        return metadata["app_port"] if metadata else None
