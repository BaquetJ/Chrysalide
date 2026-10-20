"""Lecture et diagnostic structurel des notebooks Jupyter."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class NotebookFormatError(ValueError):
    """Raised when a file is not a supported Jupyter notebook."""


@dataclass(frozen=True)
class NotebookSummary:
    """Structural facts about a notebook, collected without executing it."""

    path: Path
    total_cells: int
    code_cells: int
    markdown_cells: int
    raw_cells: int
    code_cells_with_outputs: int


def inspect_notebook(path: str | Path) -> NotebookSummary:
    """Read a notebook and return a structural summary without changing it."""
    notebook_path = Path(path)
    try:
        notebook: Any = json.loads(notebook_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise NotebookFormatError(
            f"Le fichier n'est pas un JSON valide (ligne {error.lineno}, colonne {error.colno})."
        ) from error
    except UnicodeDecodeError as error:
        raise NotebookFormatError("Le fichier doit être encodé en UTF-8.") from error

    if not isinstance(notebook, dict):
        raise NotebookFormatError("Le contenu du fichier doit être un objet JSON.")
    if notebook.get("nbformat") != 4:
        raise NotebookFormatError("Seuls les notebooks Jupyter au format 4 sont pris en charge.")

    cells = notebook.get("cells")
    if not isinstance(cells, list):
        raise NotebookFormatError("Le notebook doit contenir une liste de cellules.")

    counts = {"code": 0, "markdown": 0, "raw": 0}
    code_cells_with_outputs = 0
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            raise NotebookFormatError(f"La cellule {index} doit être un objet JSON.")

        cell_type = cell.get("cell_type")
        if not isinstance(cell_type, str) or cell_type not in counts:
            raise NotebookFormatError(
                f"Type de cellule non pris en charge à l'index {index}: {cell_type!r}."
            )
        counts[cell_type] += 1

        source = cell.get("source")
        if not isinstance(source, (str, list)) or (
            isinstance(source, list) and not all(isinstance(part, str) for part in source)
        ):
            raise NotebookFormatError(f"La source de la cellule {index} doit être du texte.")

        if cell_type == "code":
            outputs = cell.get("outputs", [])
            if not isinstance(outputs, list):
                raise NotebookFormatError(f"Les sorties de la cellule {index} doivent être une liste.")
            if outputs:
                code_cells_with_outputs += 1

    return NotebookSummary(
        path=notebook_path,
        total_cells=len(cells),
        code_cells=counts["code"],
        markdown_cells=counts["markdown"],
        raw_cells=counts["raw"],
        code_cells_with_outputs=code_cells_with_outputs,
    )
