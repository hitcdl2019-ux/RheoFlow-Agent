#!/usr/bin/env bash
set -euo pipefail

IMAGE=${IMAGE:-foamagent-dual-openfoam@sha256:c15f3b22d2bcc648b95ae0e2ef929bfb88723eb901b51de4e1b2719945650e5d}
ARTIFACT_DIR=${ARTIFACT_DIR:-runs/premerge-checks}
if [[ -n "${FOAMAGENT_DEV_ALLOW_UNSTAMPED:-}" ]]; then
    echo "FOAMAGENT_DEV_ALLOW_UNSTAMPED must not be set during premerge checks" >&2
    exit 1
fi
PYTEST_TARGETS=${PYTEST_TARGETS:-tests/test_workflow_compiler.py tests/test_case_manifest.py tests/test_mixed_session_isolation.py tests/test_business_prompt_expectations.py tests/test_intake.py tests/test_intake_business_cases.py tests/test_source_authenticity_cases.py tests/test_material_cards.py tests/test_main_requires_intake.py tests/test_agent_requirement_golden.py}
mkdir -p "$ARTIFACT_DIR"

run_in_container() {
    docker run --rm -v "$PWD:/workspace/repo" --entrypoint /bin/bash "$IMAGE" -lc "$1"
}

echo "==> RAG metadata audit"
run_in_container 'cd /workspace/repo && /opt/conda/envs/FoamAgent/bin/python scripts/audit_rag_metadata.py --output runs/premerge-checks/rag_inventory.json'

echo "==> Offline routing, manifest, business prompt, and mixed-session tests"
run_in_container "set -euo pipefail
PY=/opt/conda/envs/FoamAgent/bin/python
\"\$PY\" -m pytest --version >/dev/null 2>&1 || \"\$PY\" -m pip install --no-cache-dir pytest==8.3.5
cd /workspace/repo
\"\$PY\" -m pytest -q $PYTEST_TARGETS"

echo "==> Seven certified solver regression"
ARTIFACT_DIR="$ARTIFACT_DIR/dual-channel-regression" IMAGE="$IMAGE" ./scripts/run_dual_channel_regression.sh

if command -v id >/dev/null 2>&1; then
    docker run --rm -v "$PWD:/workspace/repo" --entrypoint /bin/bash "$IMAGE" -lc         "chown -R $(id -u):$(id -g) /workspace/repo/$ARTIFACT_DIR 2>/dev/null || true"
fi

echo "==> Premerge checks passed"
