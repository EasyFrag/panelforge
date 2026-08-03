import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))


class PackageImportTest(unittest.TestCase):
    def test_package_imports(self):
        import panelforge

        self.assertEqual(panelforge.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
