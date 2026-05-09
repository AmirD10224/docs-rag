"""GET /evals, return the latest persisted eval scorecard.

Eval reports are written as JSON files into `evals/reports/` by
`evals/run.py`. This endpoint reads the most recent one and returns
it. We surface a 404 (not 500) if there's no report yet, the
frontend renders an "evals not yet run" state.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from fastapi import APIRouter, HTTPException, Request, status

from docs_rag.deps import Container
from docs_rag.synthesis.schema import EvalReport

router = APIRouter(prefix="/evals", tags=["evals"])


@router.get("", response_model=EvalReport)
async def latest(request: Request) -> EvalReport:
    container = cast(Container, request.app.state.container)
    settings = container.settings
    reports_dir = settings.project_root / "evals" / "reports"
    if not reports_dir.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no eval reports")

    candidates = sorted(
        (p for p in reports_dir.glob("*.json") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no eval reports")

    payload = json.loads(_read(candidates[0]))
    return EvalReport.model_validate(payload)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")
