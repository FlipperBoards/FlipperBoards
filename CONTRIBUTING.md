# Contributing to FlipperBoards

Thanks for your interest! FlipperBoards is a source-available split-flap
display app — contributions of all kinds are welcome: bug reports, docs,
new display modes, and code.

## Getting started

```bash
git clone https://github.com/FlipperBoards/FlipperBoards
cd FlipperBoards

# Backend
pip install -r backend/requirements-dev.txt
cd backend && python main.py          # http://localhost:8000

# Frontend (separate terminal — proxies /api and /ws to :8000)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## Before you open a PR

1. **Tests pass:** `cd backend && pytest tests`
2. **Lint passes:** `cd backend && ruff check .`
3. **Frontend builds:** `cd frontend && npm run build`
4. Add tests for new backend behavior — the suite in `backend/tests/`
   shows the patterns (real app under lifespan, throwaway DB).

CI runs all three on every PR; green checks are required.

## What makes a good PR

- One logical change per PR — small PRs get reviewed fast
- A clear description of the problem and the approach
- For UI changes: a screenshot or short clip
- For new display modes: consider a plugin first (see [PLUGINS.md](PLUGINS.md))
  — modes that need external accounts or niche APIs usually belong there

## Reporting bugs

Use the issue templates. The most useful bug reports include: how you're
running it (Docker/bare metal/version), the screen size, and backend logs
(`docker compose logs` or `journalctl -u flipperboards-backend`).

## Licensing

By contributing you agree your contribution is licensed under the project's
[Sustainable Use License](LICENSE.md).
