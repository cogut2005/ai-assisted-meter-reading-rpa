from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RuntimePaths:
    project_root: Path
    input_path: Path
    db_path: Path
    output_dir: Path
