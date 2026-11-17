#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

cat > README.md <<'__H_RM__'
# VentureOS

An open-source team of AI agents that takes a founder's idea toward a validated, sellable digital product — and says "don't launch this" when the evidence is weak.

Built for **MADS × CSEA AI Hackathon Fall 2026**.

## Quickstart

```bash
docker compose up