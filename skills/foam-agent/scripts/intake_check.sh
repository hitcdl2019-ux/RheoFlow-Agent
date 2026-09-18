#!/usr/bin/env bash
set -euo pipefail

REQ=${1:-}
if [[ -z "$REQ" ]]; then
  echo "Usage: $0 path/to/user_requirement.txt" >&2
  exit 2
fi
if [[ ! -f "$REQ" ]]; then
  echo "Requirement file not found: $REQ" >&2
  exit 2
fi
REQ_DIR=$(cd "$(dirname "$REQ")" && pwd)
REQ="$REQ_DIR/$(basename "$REQ")"

is_foam_agent_root() {
  [[ -f "$1/scripts/foamagent_intake.py" && -d "$1/src" ]]
}

find_repo_root() {
  local dir="$PWD"
  while [[ "$dir" != "/" ]]; do
    if is_foam_agent_root "$dir"; then
      printf '%s\n' "$dir"
      return 0
    fi
    dir=$(dirname "$dir")
  done

  for candidate in \
    /data/chendl/cfd_project/Foam-Agent \
    /data/chendl/Foam-Agent \
    "$HOME/cfd_project/Foam-Agent" \
    "$HOME/Foam-Agent"; do
    if is_foam_agent_root "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

REPO_ROOT=${FOAM_AGENT_REPO_ROOT:-}
if [[ -n "$REPO_ROOT" && ! -d "$REPO_ROOT" ]]; then
  echo "FOAM_AGENT_REPO_ROOT does not exist: $REPO_ROOT" >&2
  exit 2
fi
if [[ -n "$REPO_ROOT" && ! -f "$REPO_ROOT/scripts/foamagent_intake.py" ]]; then
  echo "FOAM_AGENT_REPO_ROOT is not a Foam-Agent repo: $REPO_ROOT" >&2
  exit 2
fi
if [[ -z "$REPO_ROOT" ]]; then
  REPO_ROOT=$(find_repo_root) || {
    echo "Cannot find Foam-Agent repo root. Set FOAM_AGENT_REPO_ROOT=/path/to/Foam-Agent." >&2
    exit 2
  }
fi

is_executable_python() {
  local candidate="$1"
  if [[ "$candidate" == */* ]]; then
    [[ -x "$candidate" ]]
  else
    command -v "$candidate" >/dev/null 2>&1
  fi
}

python_has_pydantic() {
  local candidate="$1"
  "$candidate" - <<'PY' >/dev/null 2>&1
import pydantic
PY
}

validate_python() {
  local label="$1"
  local candidate="$2"
  if ! is_executable_python "$candidate"; then
    echo "$label is not executable: $candidate" >&2
    exit 2
  fi
  if ! python_has_pydantic "$candidate"; then
    echo "$label does not provide Foam-Agent dependencies: $candidate" >&2
    echo "Missing Python module: pydantic" >&2
    exit 2
  fi
  printf '%s\n' "$candidate"
}

find_python() {
  if [[ -n "${FOAM_AGENT_PYTHON:-}" ]]; then
    validate_python "FOAM_AGENT_PYTHON" "$FOAM_AGENT_PYTHON"
    return 0
  fi
  if [[ -n "${PYTHON:-}" ]]; then
    validate_python "PYTHON" "$PYTHON"
    return 0
  fi

  local candidates=(
    "$REPO_ROOT/.venv/bin/python"
    "$REPO_ROOT/venv/bin/python"
    /opt/conda/envs/FoamAgent/bin/python
    /opt/conda/envs/foamagent/bin/python
    /opt/conda/envs/Foam-Agent/bin/python
    "$HOME/miniconda3/envs/FoamAgent/bin/python"
    "$HOME/miniconda3/envs/foamagent/bin/python"
    "$HOME/anaconda3/envs/FoamAgent/bin/python"
    "$HOME/anaconda3/envs/foamagent/bin/python"
    /opt/conda/bin/python
    python3
  )

  local candidate
  for candidate in "${candidates[@]}"; do
    if is_executable_python "$candidate" && python_has_pydantic "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

container_is_running() {
  local container="$1"
  docker ps --format '{{.Names}}' | grep -qx "$container"
}

container_has_foam_agent() {
  local container="$1"
  docker exec "$container" test -f /opt/Foam-Agent/scripts/foamagent_intake.py >/dev/null 2>&1
}

container_has_python() {
  local container="$1"
  docker exec "$container" /opt/conda/envs/FoamAgent/bin/python - <<'PY' >/dev/null 2>&1
import pydantic
PY
}

validate_container() {
  local label="$1"
  local container="$2"
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not available; cannot use $label: $container" >&2
    exit 2
  fi
  if ! container_is_running "$container"; then
    echo "$label is not a running container: $container" >&2
    exit 2
  fi
  if ! container_has_foam_agent "$container"; then
    echo "$label does not contain /opt/Foam-Agent: $container" >&2
    exit 2
  fi
  if ! container_has_python "$container"; then
    echo "$label does not provide Foam-Agent Python dependencies: $container" >&2
    echo "Missing Python module in container: pydantic" >&2
    exit 2
  fi
  printf '%s\n' "$container"
}

find_container() {
  if [[ -n "${FOAM_AGENT_CONTAINER:-}" ]]; then
    validate_container "FOAM_AGENT_CONTAINER" "$FOAM_AGENT_CONTAINER"
    return 0
  fi
  if ! command -v docker >/dev/null 2>&1; then
    return 1
  fi

  local container
  for container in foamagent_dual_dev; do
    if container_is_running "$container" && container_has_foam_agent "$container" && container_has_python "$container"; then
      printf '%s\n' "$container"
      return 0
    fi
  done

  while IFS=$'\t' read -r container image; do
    case "$image" in
      foamagent-dual-openfoam:pytest-check|foamagent-dual-openfoam:v1)
        if container_has_foam_agent "$container" && container_has_python "$container"; then
          printf '%s\n' "$container"
          return 0
        fi
        ;;
    esac
  done < <(docker ps --format '{{.Names}}\t{{.Image}}')

  return 1
}

map_host_path_to_container() {
  local path="$1"
  case "$path" in
    "$REPO_ROOT"/*)
      printf '/opt/Foam-Agent/%s\n' "${path#"$REPO_ROOT"/}"
      return 0
      ;;
    "$HOME/.codex"/*)
      printf '/root/.codex/%s\n' "${path#"$HOME/.codex"/}"
      return 0
      ;;
    /data/chendl/workspace/*)
      printf '/workspace/%s\n' "${path#/data/chendl/workspace/}"
      return 0
      ;;
  esac
  return 1
}

run_in_container() {
  local container="$1"
  local container_req
  if container_req=$(map_host_path_to_container "$REQ"); then
    docker exec -w /opt/Foam-Agent "$container" \
      /opt/conda/envs/FoamAgent/bin/python \
      scripts/foamagent_intake.py "$container_req" --write-receipt
    return $?
  fi

  local container_dir="/tmp/foamagent-intake-$$"
  local container_req_tmp="$container_dir/user_requirement.txt"
  docker exec "$container" mkdir -p "$container_dir"
  docker cp "$REQ" "$container:$container_req_tmp"
  docker exec -w /opt/Foam-Agent "$container" \
    /opt/conda/envs/FoamAgent/bin/python \
    scripts/foamagent_intake.py "$container_req_tmp" --write-receipt
  local status=$?
  if [[ "$status" -eq 0 ]]; then
    docker cp "$container:$container_req_tmp.intake.json" "$REQ.intake.json" >/dev/null
  fi
  return "$status"
}

if PY=$(find_python); then
  cd "$REPO_ROOT"
  PYTHONPATH=src "$PY" scripts/foamagent_intake.py "$REQ" --write-receipt
elif CONTAINER=$(find_container); then
  run_in_container "$CONTAINER"
else
  echo "Cannot find a Python environment with Foam-Agent dependencies." >&2
  echo "Missing Python module: pydantic" >&2
  echo "Set FOAM_AGENT_PYTHON=/path/to/FoamAgent/bin/python, create $REPO_ROOT/.venv, or start foamagent_dual_dev from foamagent-dual-openfoam:pytest-check." >&2
  exit 2
fi
