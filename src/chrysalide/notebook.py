"""Lecture et diagnostic structurel des notebooks Jupyter."""

from __future__ import annotations

import ast
import json
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_READ_FUNCTIONS = {
    "read_csv",
    "read_excel",
    "read_feather",
    "read_hdf",
    "read_json",
    "read_parquet",
    "read_pickle",
    "read_table",
    "read_text",
    "read_bytes",
    "loadtxt",
    "genfromtxt",
}
_WRITE_FUNCTIONS = {
    "to_csv",
    "to_excel",
    "to_feather",
    "to_hdf",
    "to_json",
    "to_parquet",
    "to_pickle",
    "write_text",
    "write_bytes",
}
_CHECK_FUNCTIONS = {"is_file", "is_dir"}
_PATH_ARGUMENT_NAMES = {
    "file",
    "filename",
    "filepath",
    "filepath_or_buffer",
    "path",
    "path_or_buf",
}


class NotebookFormatError(ValueError):
    """Raised when a file is not a supported Jupyter notebook."""


@dataclass(frozen=True)
class NotebookFileReference:
    """A statically detected file access in a notebook code cell."""

    expression: str
    operation: str
    cell_number: int
    availability: str


@dataclass(frozen=True)
class NotebookSummary:
    """Structural facts about a notebook, collected without executing it."""

    path: Path
    project_dir: Path
    total_cells: int
    code_cells: int
    markdown_cells: int
    raw_cells: int
    code_cells_with_outputs: int
    imported_modules: tuple[str, ...]
    standard_modules: tuple[str, ...]
    project_modules: tuple[str, ...]
    other_modules: tuple[str, ...]
    file_references: tuple[NotebookFileReference, ...]
    unanalyzed_code_cells: int


def _static_path_value(node: ast.AST, aliases: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return aliases.get(node.id)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == "Path" and len(node.args) == 1:
            return _static_path_value(node.args[0], aliases)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if ast.unparse(node.func) == "pathlib.Path" and len(node.args) == 1:
            return _static_path_value(node.args[0], aliases)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _static_path_value(node.left, aliases)
        right = _static_path_value(node.right, aliases)
        if left is not None and right is not None:
            return str(Path(left) / right)
    if isinstance(node, ast.Call) and ast.unparse(node.func) in {
        "os.path.join",
        "ntpath.join",
        "posixpath.join",
    }:
        parts = [_static_path_value(argument, aliases) for argument in node.args]
        if parts and all(part is not None for part in parts):
            return str(Path(parts[0]).joinpath(*parts[1:]))
    return None


def _file_availability(path_expression: str | None, notebook_directory: Path) -> str:
    if path_expression is None:
        return "chemin dynamique, non vérifié"

    candidate = Path(path_expression)
    if not candidate.is_absolute():
        candidate = notebook_directory / candidate

    try:
        candidate.stat()
    except FileNotFoundError:
        return "absent à l'emplacement vérifié"
    except OSError:
        return "impossible à vérifier"
    return "présent à l'emplacement vérifié"


def _import_groups(
    imported_modules: set[str], notebook_directory: Path
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    standard_modules = set(sys.stdlib_module_names)
    standard: set[str] = set()
    project: set[str] = set()
    other: set[str] = set()

    for module in imported_modules:
        root_module = module.lstrip(".").split(".", maxsplit=1)[0]
        if module.startswith("."):
            project.add(module)
        elif root_module in standard_modules:
            standard.add(module)
        elif (
            (notebook_directory / root_module).is_dir()
            or (notebook_directory / f"{root_module}.py").is_file()
        ):
            project.add(module)
        else:
            other.add(module)

    return tuple(sorted(standard)), tuple(sorted(project)), tuple(sorted(other))


def _called_function_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _file_reference(
    call: ast.Call,
    cell_number: int,
    path_aliases: dict[str, str],
    notebook_directory: Path,
) -> NotebookFileReference | None:
    function_name = _called_function_name(call)
    if function_name in _READ_FUNCTIONS:
        operation = "lecture"
    elif function_name in _WRITE_FUNCTIONS:
        operation = "écriture"
    elif function_name in _CHECK_FUNCTIONS:
        operation = "vérification"
    elif function_name == "open":
        mode = next(
            (keyword.value for keyword in call.keywords if keyword.arg == "mode"),
            call.args[1] if len(call.args) > 1 else None,
        )
        if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
            operation = (
                "écriture" if any(flag in mode.value for flag in ("w", "a", "x")) else "lecture"
            )
        else:
            operation = "accès"
    elif function_name == "load" and isinstance(call.func, ast.Attribute):
        owner = ast.unparse(call.func.value).split(".", maxsplit=1)[0]
        if owner not in {"joblib", "pickle", "torch"}:
            return None
        operation = "lecture"
    else:
        return None

    if isinstance(call.func, ast.Attribute) and function_name in {
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "is_file",
        "is_dir",
        "open",
    }:
        path_node = call.func.value
    elif call.args:
        path_node = call.args[0]
    else:
        path_node = next(
            (
                keyword.value
                for keyword in call.keywords
                if keyword.arg in _PATH_ARGUMENT_NAMES
            ),
            None,
        )

    if path_node is None:
        return None

    return NotebookFileReference(
        expression=ast.unparse(path_node),
        operation=operation,
        cell_number=cell_number,
        availability=_file_availability(
            _static_path_value(path_node, path_aliases),
            notebook_directory,
        ),
    )


def inspect_notebook(
    path: str | Path, *, project_dir: str | Path | None = None
) -> NotebookSummary:
    """Inspect without execution, using project_dir or the notebook's parent as context."""
    notebook_path = Path(path)
    try:
        notebook: Any = json.loads(notebook_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise NotebookFormatError(
            f"Le fichier n'est pas un JSON valide (ligne {error.lineno}, colonne {error.colno})."
        ) from error
    except UnicodeDecodeError as error:
        raise NotebookFormatError("Le fichier doit être encodé en UTF-8.") from error

    context_directory = (
        Path(project_dir) if project_dir is not None else notebook_path.parent
    ).resolve()
    if not stat.S_ISDIR(context_directory.stat().st_mode):
        raise NotADirectoryError(
            f"Le dossier du projet n'est pas un répertoire : {context_directory}"
        )

    if not isinstance(notebook, dict):
        raise NotebookFormatError("Le contenu du fichier doit être un objet JSON.")
    if notebook.get("nbformat") != 4:
        raise NotebookFormatError("Seuls les notebooks Jupyter au format 4 sont pris en charge.")

    cells = notebook.get("cells")
    if not isinstance(cells, list):
        raise NotebookFormatError("Le notebook doit contenir une liste de cellules.")

    counts = {"code": 0, "markdown": 0, "raw": 0}
    code_cells_with_outputs = 0
    imported_modules: set[str] = set()
    file_references: set[NotebookFileReference] = set()
    unanalyzed_code_cells = 0
    path_aliases: dict[str, str] = {}
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
                raise NotebookFormatError(
                    f"Les sorties de la cellule {index} doivent être une liste."
                )
            if outputs:
                code_cells_with_outputs += 1
            source_text = source if isinstance(source, str) else "".join(source)
            try:
                syntax_tree = ast.parse(source_text)
            except SyntaxError:
                unanalyzed_code_cells += 1
                continue

            cell_number = index + 1
            for node in ast.walk(syntax_tree):
                if isinstance(node, ast.Import):
                    imported_modules.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imported_modules.add("." * node.level + (node.module or ""))

            for statement in syntax_tree.body:
                for node in ast.walk(statement):
                    if isinstance(node, ast.Call):
                        reference = _file_reference(
                            node,
                            cell_number,
                            path_aliases,
                            context_directory,
                        )
                        if reference is not None:
                            file_references.add(reference)

                if isinstance(statement, ast.Assign):
                    value = _static_path_value(statement.value, path_aliases)
                    for target in statement.targets:
                        if isinstance(target, ast.Name):
                            if value is None:
                                path_aliases.pop(target.id, None)
                            else:
                                path_aliases[target.id] = value
                elif isinstance(statement, ast.AnnAssign) and isinstance(
                    statement.target, ast.Name
                ):
                    value = _static_path_value(statement.value, path_aliases)
                    if value is None:
                        path_aliases.pop(statement.target.id, None)
                    else:
                        path_aliases[statement.target.id] = value

    standard_modules, project_modules, other_modules = _import_groups(
        imported_modules,
        context_directory,
    )

    return NotebookSummary(
        path=notebook_path,
        project_dir=context_directory,
        total_cells=len(cells),
        code_cells=counts["code"],
        markdown_cells=counts["markdown"],
        raw_cells=counts["raw"],
        code_cells_with_outputs=code_cells_with_outputs,
        imported_modules=tuple(sorted(imported_modules)),
        standard_modules=standard_modules,
        project_modules=project_modules,
        other_modules=other_modules,
        file_references=tuple(
            sorted(
                file_references,
                key=lambda item: (
                    item.cell_number,
                    item.operation,
                    item.expression,
                    item.availability,
                ),
            )
        ),
        unanalyzed_code_cells=unanalyzed_code_cells,
    )
