import json
import tempfile
import unittest
from pathlib import Path

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
