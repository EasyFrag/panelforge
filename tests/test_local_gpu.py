import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from panelforge.infrastructure.local_gpu import NvidiaSmiMonitor


class NvidiaSmiMonitorTest(unittest.TestCase):
    def test_reads_and_normalizes_local_gpu_stats(self):
        calls = []

        def run(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="NVIDIA GeForce RTX 5090, 32607, 30000, 2188, 67\n",
                stderr="",
            )

        monitor = NvidiaSmiMonitor(runner=run, cache_seconds=0)
        stats = monitor.get_stats()

        self.assertEqual(stats.name, "NVIDIA GeForce RTX 5090")
        self.assertEqual(stats.total_bytes, 32_607 * 1024**2)
        self.assertEqual(stats.used_bytes, 30_000 * 1024**2)
        self.assertEqual(stats.free_bytes, 2_188 * 1024**2)
        self.assertEqual(stats.used_percent, 92.0)
        self.assertEqual(stats.temperature_c, 67.0)
        self.assertEqual(calls[0][0][0:2], ["nvidia-smi", "--id=0"])
        self.assertEqual(calls[0][1]["timeout"], 2.0)
        self.assertTrue(calls[0][1]["check"])

    def test_reuses_a_recent_snapshot(self):
        call_count = 0

        def run(command, **kwargs):
            nonlocal call_count
            call_count += 1
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="NVIDIA GeForce RTX 5090, 32607, 12000, 20607, 55\n",
                stderr="",
            )

        monitor = NvidiaSmiMonitor(runner=run, cache_seconds=10)

        self.assertIs(monitor.get_stats(), monitor.get_stats())
        self.assertEqual(call_count, 1)

    def test_rejects_an_unexpected_response(self):
        def run(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, stdout="N/A\n", stderr="")

        monitor = NvidiaSmiMonitor(runner=run, cache_seconds=0)

        with self.assertRaisesRegex(ValueError, "unexpected nvidia-smi output"):
            monitor.get_stats()


if __name__ == "__main__":
    unittest.main()
