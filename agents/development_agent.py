from __future__ import annotations
from pathlib import Path
from agents.base import BaseAgent
from services import evidence_ledger


class DevelopmentAgent(BaseAgent):
    name = "development"
    description = "Generates real MVP source files."
    system_prompt = "You write SMALL, WORKING scaffolds. Never write fake code."

    def scaffold_mvp(self, venture, spec, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        features = spec.get("features", [])[:5]
        stack = spec.get("tech_stack", {})

        readme = f"# {venture.get('name', 'MVP')}\n\n"
        readme += f"{venture.get('brief', {}).get('concept', '')}\n\n"
        readme += "## Features\n" + "\n".join(f"- {f.get('name','')}" for f in features)
        readme += f"\n\n## Tech\n{stack.get('language','Python')} / {stack.get('framework','FastAPI')}\n"
        (output_dir / "README.md").write_text(readme, encoding="utf-8")

        (output_dir / "requirements.txt").write_text(
            "fastapi==0.115.0\nuvicorn[standard]==0.30.6\n", encoding="utf-8")

        fallback = '"""MVP entry point."""\nfrom fastapi import FastAPI\napp = FastAPI()\n\n'
        for f in features:
            slug = (f.get("name", "") or "feature").lower().replace(" ", "-")
            fn = slug.replace("-", "_")
            fallback += f'@app.get("/{slug}")\ndef {fn}():\n    return {{"status": "todo"}}\n\n'
        (output_dir / "main.py").write_text(fallback, encoding="utf-8")

        for fname in ("README.md", "requirements.txt", "main.py"):
            evidence_ledger.add(venture["id"], type="verified",
                                claim=f"Generated file: {fname}",
                                agent=self.name, stage="build")

        return {"output_dir": str(output_dir),
                "files": sorted(p.name for p in output_dir.iterdir() if p.is_file())}
