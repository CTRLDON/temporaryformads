from __future__ import annotations
import subprocess, sys
from pathlib import Path
from agents.base import BaseAgent
from services import evidence_ledger


class TestingAgent(BaseAgent):
    name = "testing"
    description = "Writes and runs smoke tests for the MVP."
    system_prompt = "You write minimal working tests."

    def generate_smoke_test(self, venture, spec, output_dir: Path):
        test_file = output_dir / "test_smoke.py"
        test_file.write_text(
            '"""Smoke test."""\nimport sys\nfrom pathlib import Path\n'
            "sys.path.insert(0, str(Path(__file__).parent))\n"
            "from main import app  # noqa\n\n"
            "def test_app_has_routes():\n"
            "    assert len([r.path for r in app.routes]) >= 1\n",
            encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(test_file), "-q", "--no-header"],
                capture_output=True, text=True, timeout=30, cwd=str(output_dir))
            passed = result.returncode == 0
            output = (result.stdout or result.stderr)[-500:]
        except Exception as e:
            passed, output = False, str(e)

        evidence_ledger.add(venture["id"],
                            type="experimental" if passed else "assumption",
                            claim=f"Test run: {'PASSED' if passed else 'FAILED'}",
                            details=output, agent=self.name, stage="build")
        return {"test_file": test_file.name, "passed": passed, "output": output}
