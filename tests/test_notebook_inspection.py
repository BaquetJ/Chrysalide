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
                {"cell_type": "code", "source": ["print('hello')"], "outputs": [{"output_type": "stream"}]},
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
