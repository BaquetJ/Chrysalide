import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from chrysalide.cli import main
from chrysalide.notebook import NotebookFormatError, inspect_notebook


class InspectNotebookTests(unittest.TestCase):
    def write_notebook(self, directory: str, notebook: object) -> Path:
        path = Path(directory) / "example.ipynb"
        path.write_text(json.dumps(notebook), encoding="utf-8")
        return path

    def test_counts_cell_types_and_saved_outputs(self) -> None:
        notebook = {
            "nbformat": 4,
            "cells": [
                {"cell_type": "markdown", "source": ["# Analysis"]},
                {
                    "cell_type": "code",
                    "source": ["print('hello')"],
                    "outputs": [{"output_type": "stream"}],
                },
                {"cell_type": "code", "source": "", "outputs": []},
                {"cell_type": "raw", "source": "notes"},
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            summary = inspect_notebook(self.write_notebook(directory, notebook))

        self.assertEqual(summary.total_cells, 4)
        self.assertEqual(summary.code_cells, 2)
        self.assertEqual(summary.markdown_cells, 1)
        self.assertEqual(summary.raw_cells, 1)
        self.assertEqual(summary.code_cells_with_outputs, 1)

    def test_detects_imports_and_file_references_without_execution(self) -> None:
        notebook = {
            "nbformat": 4,
            "cells": [
                {
                    "cell_type": "code",
                    "source": [
                        "import pandas as pd\n",
                        "from pathlib import Path\n",
                        "DATA_DIR = Path('data')\n",
                        "df = pd.read_csv(DATA_DIR / 'train.csv')\n",
                        "df.to_csv('result.csv')\n",
                        "with open('settings.json', mode='r') as stream:\n",
                        "    config = stream.read()\n",
                    ],
                    "outputs": [],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            summary = inspect_notebook(self.write_notebook(directory, notebook))

        self.assertEqual(summary.imported_modules, ("pandas", "pathlib"))
        self.assertCountEqual(
            [
                (reference.operation, reference.expression, reference.cell_number)
                for reference in summary.file_references
            ],
            [
                ("lecture", "DATA_DIR / 'train.csv'", 1),
                ("écriture", "'result.csv'", 1),
                ("lecture", "'settings.json'", 1),
            ],
        )

    def test_reports_cells_with_non_python_syntax(self) -> None:
        notebook = {
            "nbformat": 4,
            "cells": [
                {"cell_type": "code", "source": ["%matplotlib inline\n"], "outputs": []},
                {"cell_type": "code", "source": ["import json"], "outputs": []},
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            summary = inspect_notebook(self.write_notebook(directory, notebook))

        self.assertEqual(summary.unanalyzed_code_cells, 1)
        self.assertEqual(summary.imported_modules, ("json",))

    def test_classifies_imports_and_checks_literal_paths_next_to_notebook(self) -> None:
        notebook = {
            "nbformat": 4,
            "cells": [
                {
                    "cell_type": "code",
                    "source": [
                        "import json\n",
                        "import pandas as pd\n",
                        "from local_package.tools import run\n",
                        "from pathlib import Path\n",
                        "DATA_DIR = Path('data')\n",
                        "df = pd.read_csv(DATA_DIR / 'train.csv')\n",
                        "df.to_csv('result.csv')\n",
                        "pd.read_csv(get_data_path())\n",
                    ],
                    "outputs": [],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "local_package").mkdir()
            (root / "data").mkdir()
            (root / "data" / "train.csv").write_text("text\n", encoding="utf-8")
            summary = inspect_notebook(self.write_notebook(directory, notebook))

        self.assertEqual(summary.standard_modules, ("json", "pathlib"))
        self.assertEqual(summary.project_modules, ("local_package.tools",))
        self.assertEqual(summary.other_modules, ("pandas",))
        references = {
            reference.expression: reference.availability
            for reference in summary.file_references
        }
        self.assertEqual(
            references["DATA_DIR / 'train.csv'"],
            "présent à l'emplacement vérifié",
        )
        self.assertEqual(
            references["'result.csv'"],
            "absent à l'emplacement vérifié",
        )
        self.assertEqual(
            references["get_data_path()"],
            "chemin dynamique, non vérifié",
        )

    def test_does_not_reuse_a_path_alias_after_dynamic_reassignment(self) -> None:
        notebook = {
            "nbformat": 4,
            "cells": [
                {
                    "cell_type": "code",
                    "source": [
                        "from pathlib import Path\n",
                        "DATA_DIR = Path('data')\n",
                        "DATA_DIR = find_data_dir()\n",
                        "import pandas as pd\n",
                        "pd.read_csv(DATA_DIR / 'train.csv')\n",
                    ],
                    "outputs": [],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "data").mkdir()
            summary = inspect_notebook(self.write_notebook(directory, notebook))

        self.assertEqual(
            summary.file_references[0].availability,
            "chemin dynamique, non vérifié",
        )

    def test_project_directory_overrides_notebook_context_without_execution(self) -> None:
        notebook = {
            "nbformat": 4,
            "cells": [{
                "cell_type": "code",
                "source": (
                    "import local_module\n"
                    "from local_package.tools import run\n"
                    "import pandas as pd\n"
                    "pd.read_csv('data.csv')\n"
                    "raise RuntimeError('must not execute')\n"
                ),
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            notebooks = root / "notebooks"
            notebooks.mkdir()
            path = self.write_notebook(str(notebooks), notebook)
            original = path.read_bytes()
            (root / "data.csv").write_text("text\n", encoding="utf-8")
            (root / "local_module.py").write_text(
                "raise RuntimeError('must not import')", encoding="utf-8"
            )
            (root / "local_package").mkdir()
            cwd = Path.cwd()

            default = inspect_notebook(path)
            summary = inspect_notebook(path, project_dir=root)

            self.assertEqual(default.project_dir, notebooks.resolve())
            self.assertEqual(default.project_modules, ())
            self.assertEqual(
                default.file_references[0].availability, "absent à l'emplacement vérifié"
            )
            self.assertEqual(summary.project_dir, root.resolve())
            self.assertEqual(
                summary.project_modules, ("local_module", "local_package.tools")
            )
            self.assertEqual(summary.other_modules, ("pandas",))
            self.assertEqual(
                summary.file_references[0].availability, "présent à l'emplacement vérifié"
            )
            self.assertEqual(Path.cwd(), cwd)
            self.assertEqual(path.read_bytes(), original)

    def test_project_context_does_not_change_absolute_file_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = root / "data.csv"
            data_path.write_text("text\n", encoding="utf-8")
            project = root / "project"
            project.mkdir()
            path = self.write_notebook(directory, {
                "nbformat": 4,
                "cells": [{"cell_type": "code", "source": f"open({str(data_path)!r})"}],
            })
            summary = inspect_notebook(path, project_dir=project)

        self.assertEqual(
            summary.file_references[0].availability, "présent à l'emplacement vérifié"
        )

    def test_relative_project_directory_is_resolved_from_current_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            notebooks = root / "notebooks"
            notebooks.mkdir()
            path = self.write_notebook(str(notebooks), {"nbformat": 4, "cells": []})
            relative_directory = os.path.relpath(root, Path.cwd())
            summary = inspect_notebook(path, project_dir=relative_directory)

        self.assertEqual(summary.project_dir, root.resolve())

    def test_rejects_missing_or_non_directory_project_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.write_notebook(directory, {"nbformat": 4, "cells": []})
            with self.assertRaises(FileNotFoundError):
                inspect_notebook(path, project_dir=root / "missing")
            with self.assertRaises(NotADirectoryError):
                inspect_notebook(path, project_dir=path)
            self.assertFalse((root / "missing").exists())

    def test_cli_passes_project_directory_and_displays_effective_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            notebooks = root / "notebooks"
            notebooks.mkdir()
            path = self.write_notebook(str(notebooks), {"nbformat": 4, "cells": []})
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["inspect", str(path), "--project-dir", str(root)])
            self.assertEqual(exit_code, 0)
            self.assertIn(f"Dossier de référence : {root.resolve()}", output.getvalue())

    def test_cli_groups_input_output_and_unconfirmed_paths(self) -> None:
        notebook = {
            "nbformat": 4,
            "cells": [{
                "cell_type": "code",
                "source": (
                    "import pandas as pd\n"
                    "from pathlib import Path\n"
                    "DATA_DIR = Path('data')\n"
                    "pd.read_csv(DATA_DIR / 'train.csv')\n"
                    "pd.read_csv(get_latest_file())\n"
                    "pd.DataFrame().to_csv('reports/result.csv')\n"
                    "Path('config.json').is_file()\n"
                ),
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            path = self.write_notebook(directory, notebook)
            output = io.StringIO()
            with redirect_stdout(output):
                main(["inspect", str(path), "--project-dir", str(root)])

        report = output.getvalue()
        self.assertIn("Fichiers lus (entrées probables) :", report)
        self.assertIn("DATA_DIR / 'train.csv'", report)
        self.assertIn("Fichiers écrits (sorties probables) :", report)
        self.assertIn("'reports/result.csv'", report)
        self.assertIn("Chemins ou accès à confirmer :", report)
        self.assertIn("get_latest_file()", report)
        self.assertIn("'config.json'", report)

    def test_cli_explains_when_no_file_references_are_found(self) -> None:
        notebook = {
            "nbformat": 4,
            "cells": [{"cell_type": "code", "source": "print('hello')"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_notebook(directory, notebook)
            output = io.StringIO()
            with redirect_stdout(output):
                main(["inspect", str(path)])

        report = output.getvalue()
        self.assertIn("Fichiers lus (entrées probables) :\n  Aucun détecté.", report)
        self.assertIn("Fichiers écrits (sorties probables) :\n  Aucun détecté.", report)
        self.assertIn("Chemins ou accès à confirmer :\n  Aucun détecté.", report)

    def test_cli_reports_missing_project_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_notebook(directory, {"nbformat": 4, "cells": []})
            error_output = io.StringIO()
            with redirect_stderr(error_output), self.assertRaises(SystemExit) as error:
                main(["inspect", str(path), "--project-dir", str(Path(directory) / "missing")])
            self.assertEqual(error.exception.code, 2)
            self.assertIn("Impossible d'accéder", error_output.getvalue())

    def test_rejects_invalid_json_with_a_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.ipynb"
            path.write_text("{invalid", encoding="utf-8")

            with self.assertRaisesRegex(NotebookFormatError, "JSON valide"):
                inspect_notebook(path)

    def test_rejects_unsupported_notebook_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_notebook(directory, {"nbformat": 3, "cells": []})

            with self.assertRaisesRegex(NotebookFormatError, "format 4"):
                inspect_notebook(path)

    def test_rejects_invalid_cell_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_notebook(
                directory,
                {"nbformat": 4, "cells": [{"cell_type": "code", "source": 12}]},
            )

            with self.assertRaisesRegex(NotebookFormatError, "source"):
                inspect_notebook(path)

    def test_rejects_non_text_cell_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_notebook(
                directory,
                {"nbformat": 4, "cells": [{"cell_type": [], "source": ""}]},
            )

            with self.assertRaisesRegex(NotebookFormatError, "Type de cellule"):
                inspect_notebook(path)


if __name__ == "__main__":
    unittest.main()
