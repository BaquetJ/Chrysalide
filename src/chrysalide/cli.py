"""Interface en ligne de commande de Chrysalide."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from chrysalide.notebook import NotebookFormatError, NotebookSummary, inspect_notebook


def _format_summary(summary: NotebookSummary) -> str:
    lines = [
        f"Notebook : {summary.path}",
        f"Cellules : {summary.total_cells}",
        (
            f"  Code : {summary.code_cells} | "
            f"Markdown : {summary.markdown_cells} | Brut : {summary.raw_cells}"
        ),
        f"Cellules de code avec des sorties enregistrées : {summary.code_cells_with_outputs}",
        f"Modules importés : {', '.join(summary.imported_modules) or 'aucun détecté'}",
        "Fichiers référencés :",
    ]
    if summary.file_references:
        lines.extend(
            f"  - {reference.operation} : {reference.expression} "
            f"(cellule {reference.cell_number})"
            for reference in summary.file_references
        )
    else:
        lines.append("  Aucun fichier détecté.")

    if summary.unanalyzed_code_cells:
        lines.append(
            "Cellules de code non analysées "
            f"(syntaxe non Python standard) : {summary.unanalyzed_code_cells}"
        )
    lines.append("Le notebook a été lu sans exécuter ni modifier ses cellules.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chrysalide")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect", help="Résumer un notebook sans l'exécuter.")
    inspect_parser.add_argument("notebook", type=Path, help="Chemin vers le fichier .ipynb.")
    arguments = parser.parse_args(argv)

    try:
        summary = inspect_notebook(arguments.notebook)
    except FileNotFoundError:
        parser.error(f"Fichier introuvable : {arguments.notebook}")
    except NotebookFormatError as error:
        parser.error(str(error))

    print(_format_summary(summary))
    return 0
