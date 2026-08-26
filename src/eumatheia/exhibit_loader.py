"""Load and parse exhibit YAML files."""

from pathlib import Path

import yaml

from .models import Exhibit


class ExhibitLoader:
    """Loads exhibit definitions from YAML files."""

    def __init__(self, exhibits_dir: Path):
        """
        Initialize exhibit loader.

        Args:
            exhibits_dir: Directory containing exhibit YAML files
        """
        self._exhibits_dir = exhibits_dir
        self._cache: dict[str, Exhibit] = {}

    def load_exhibit(self, exhibit_id: str) -> Exhibit:
        """
        Load an exhibit from YAML.

        Args:
            exhibit_id: ID of the exhibit to load

        Returns:
            Parsed Exhibit object

        Raises:
            FileNotFoundError: If exhibit file doesn't exist
            ValueError: If YAML is invalid or doesn't match schema
        """
        # Check cache first
        if exhibit_id in self._cache:
            return self._cache[exhibit_id]

        # Load from directory-based structure: exhibits/{exhibit_id}/exhibit.yaml
        exhibit_dir = self._exhibits_dir / exhibit_id
        exhibit_path = exhibit_dir / "exhibit.yaml"

        if not exhibit_path.exists():
            raise FileNotFoundError(f"Exhibit not found: {exhibit_id}")

        with open(exhibit_path, "r") as f:
            data = yaml.safe_load(f)

        # Parse and validate with pydantic
        exhibit = Exhibit.model_validate(data)

        # Verify exhibit ID matches directory name
        if exhibit.exhibit != exhibit_id:
            raise ValueError(
                f"Exhibit ID mismatch: directory={exhibit_id}, content={exhibit.exhibit}"
            )

        # Validate ancillary files exist
        self._validate_ancillary_files(exhibit, exhibit_dir)

        # Cache and return
        self._cache[exhibit_id] = exhibit
        return exhibit

    def _validate_ancillary_files(self, exhibit: Exhibit, exhibit_dir: Path) -> None:
        """
        Validate that all referenced ancillary files exist.

        Args:
            exhibit: The exhibit to validate
            exhibit_dir: Base directory for the exhibit

        Raises:
            FileNotFoundError: If any referenced ancillary file doesn't exist
        """
        for step in exhibit.steps:
            if not step.ancillary:
                continue

            # Check dockerfile
            if step.ancillary.dockerfile:
                dockerfile_path = exhibit_dir / step.ancillary.dockerfile
                if not dockerfile_path.exists():
                    raise FileNotFoundError(
                        f"Ancillary dockerfile not found for step '{step.id}': {step.ancillary.dockerfile}"
                    )

            # Check compose file
            if step.ancillary.compose:
                compose_path = exhibit_dir / step.ancillary.compose
                if not compose_path.exists():
                    raise FileNotFoundError(
                        f"Ancillary compose file not found for step '{step.id}': {step.ancillary.compose}"
                    )

            # Check scripts
            for script in step.ancillary.scripts:
                script_path = exhibit_dir / script
                if not script_path.exists():
                    raise FileNotFoundError(
                        f"Ancillary script not found for step '{step.id}': {script}"
                    )

    def get_ancillary_file_path(self, exhibit_id: str, relative_path: str) -> Path:
        """
        Resolve an ancillary file path relative to the exhibit directory.

        Args:
            exhibit_id: ID of the exhibit
            relative_path: Relative path to the ancillary file

        Returns:
            Absolute path to the ancillary file
        """
        return self._exhibits_dir / exhibit_id / relative_path

    def clear_cache(self) -> None:
        """Clear the exhibit cache (useful for development/testing)."""
        self._cache.clear()
