from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.agent_quality_service import agent_quality_service


def main() -> int:
    run = agent_quality_service.run_evaluation(execution_mode="offline")
    summary = {
        "dataset_id": run.dataset_id,
        "dataset_version": run.dataset_version,
        "execution_mode": run.execution_mode,
        "passed_cases": run.passed_cases,
        "total_cases": run.total_cases,
        "pass_rate": run.pass_rate,
        "admitted": run.admission.admitted,
        "failed_critical_case_ids": run.admission.failed_critical_case_ids,
        "failure_reasons": run.admission.failure_reasons,
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if run.admission.admitted else 1


if __name__ == "__main__":
    raise SystemExit(main())
