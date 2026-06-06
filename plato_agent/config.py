"""Configuration loader for Plato rooms."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RoomConfig:
    """Configuration for a single Plato room connection.

    Attributes:
        name: Human-readable room name.
        host: Room host address.
        port: Room port number.
        sensors: Sensor definitions and thresholds.
        actuators: Actuator definitions.
        metadata: Additional room metadata (location, type, etc.).
    """

    name: str = ""
    host: str = "localhost"
    port: int = 7000
    sensors: dict[str, Any] = field(default_factory=dict)
    actuators: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str | Path) -> RoomConfig:
        """Load room configuration from a JSON file (.room.json).

        Args:
            path: Path to the JSON configuration file.

        Returns:
            RoomConfig instance.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the JSON is malformed.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Room config not found: {path}")

        with open(path) as f:
            data = json.load(f)

        return cls(
            name=data.get("name", path.stem.replace(".room", "")),
            host=data.get("host", "localhost"),
            port=data.get("port", 7000),
            sensors=data.get("sensors", {}),
            actuators=data.get("actuators", {}),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def load_directory(cls, directory: str | Path) -> list[RoomConfig]:
        """Load all .room.json files from a directory.

        Args:
            directory: Directory path to scan.

        Returns:
            List of RoomConfig instances.
        """
        directory = Path(directory)
        configs = []
        if not directory.exists():
            return configs
        for path in sorted(directory.glob("*.room.json")):
            configs.append(cls.from_file(path))
        return configs
