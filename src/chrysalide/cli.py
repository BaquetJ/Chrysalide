"""Interface en ligne de commande de Chrysalide."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from chrysalide.notebook import NotebookFormatError, NotebookSummary, inspect_notebook


def _format_summary(summary: NotebookSummary) -> str:
    lines = [
        f"Notebook : {summary.path}",
        f"Dossier de référence : {summary.project_dir}",
        f"Cellules : {summary.total_cells}",
        (
            f"  Code : {summary.code_cells} | "
            f"Markdown : {summary.markdown_cells} | Brut : {summary.raw_cells}"
        ),
        f"Cellules de code avec des sorties enregistrées : {summary.code_cells_with_outputs}",
        f"Modules importés : {', '.join(summary.imported_modules) or 'aucun détecté'}",
        "Bilan des prérequis (déduit du code, à confirmer) :",
        f"  Bibliothèque standard : {', '.join(summary.standard_modules) or 'aucune détectée'}",
        f"  Modules du projet repérés : {', '.join(summary.project_modules) or 'aucun détecté'}",
        f"  Autres imports à vérifier : {', '.join(summary.other_modules) or 'aucun détecté'}",
    ]

    inputs = [
        reference
        for reference in summary.file_references
        if reference.operation == "lecture"
        and reference.availability != "chemin dynamique, non vérifié"
    ]
    outputs = [
        reference
        for reference in summary.file_references
        if reference.operation == "écriture"
        and reference.availability != "chemin dynamique, non vérifié"
    ]
    to_confirm = [
        reference
        for reference in summary.file_references
        if reference not in inputs and reference not in outputs
    ]

    for title, references in (
        ("Fichiers lus (entrées probables)", inputs),
        ("Fichiers écrits (sorties probables)", outputs),
        ("Chemins ou accès à confirmer", to_confirm),
    ):
        lines.append(f"{title} :")
        if references:
            lines.extend(
                f"  - {reference.expression} "
                f"(cellule {reference.cell_number}, {reference.availability})"
                for reference in references
            )
        else:
            lines.append("  Aucun détecté.")

    if summary.unanalyzed_code_cells:
        lines.append(
            "Cellules de code non analysées "
            f"(syntaxe non Python standard) : {summary.unanalyzed_code_cells}"
        )
    lines.append(
        "Le classement est déduit des appels repérés : vérifie-le selon l'usage réel du code."
    )
    lines.append(
        "La présence des chemins relatifs est vérifiée depuis ce dossier de référence ; "
        "le dossier d'exécution peut être différent."
    )
    lines.append(
        "Les imports sont déduits du code ; aucun paquet n'est installé ni généré automatiquement."
    )
    lines.append("Le notebook a été lu sans exécuter ni modifier ses cellules.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chrysalide")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect", help="Résumer un notebook sans l'exécuter.")
    inspect_parser.add_argument("notebook", type=Path, help="Chemin vers le fichier .ipynb.")
    inspect_parser.add_argument(
        "--project-dir",
        type=Path,
        help=(
            "Dossier de référence pour les fichiers et modules locaux "
            "(défaut : dossier du notebook)."
        ),
    )
    arguments = parser.parse_args(argv)

    try:
        summary = inspect_notebook(arguments.notebook, project_dir=arguments.project_dir)
    except OSError as error:
        parser.error(f"Impossible d'accéder au notebook ou au dossier du projet : {error}")
    except NotebookFormatError as error:
        parser.error(str(error))

    print(_format_summary(summary))
    return 0
