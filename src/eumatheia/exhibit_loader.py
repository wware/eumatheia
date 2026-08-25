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

        # Load from file
        exhibit_path = self._exhibits_dir / f"{exhibit_id}.yaml"
        if not exhibit_path.exists():
            raise FileNotFoundError(f"Exhibit not found: {exhibit_id}")

        with open(exhibit_path, "r") as f:
            data = yaml.safe_load(f)

        # Parse and validate with pydantic
        exhibit = Exhibit.model_validate(data)

        # Verify exhibit ID matches filename
        if exhibit.exhibit != exhibit_id:
            raise ValueError(
                f"Exhibit ID mismatch: file={exhibit_id}, content={exhibit.exhibit}"
            )

        # Cache and return
        self._cache[exhibit_id] = exhibit
        return exhibit

    def clear_cache(self) -> None:
        """Clear the exhibit cache (useful for development/testing)."""
        self._cache.clear()
