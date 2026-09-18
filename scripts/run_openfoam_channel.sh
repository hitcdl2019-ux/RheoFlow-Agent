#!/usr/bin/env bash
set -euo pipefail

channel=${1:?usage: run_openfoam_channel.sh <v9-rheotool|v10-foundation> command [args...]}
shift

case "$channel" in
  v9-rheotool) bashrc=/opt/openfoam9/etc/bashrc; extra=/etc/profile.d/rheotool.sh ;;
  v10-foundation) bashrc=/opt/openfoam10/etc/bashrc; extra= ;;
  *) echo "unsupported OpenFOAM channel: $channel" >&2; exit 2 ;;
esac

[[ -r "$bashrc" ]] || { echo "OpenFOAM environment not found: $bashrc" >&2; exit 3; }

exec env -i HOME="${HOME:-/tmp}" TERM="${TERM:-dumb}" PATH=/usr/bin:/bin \
  bash --noprofile --norc -c 'source "$1" >/dev/null 2>&1; [[ -z "$2" ]] || source "$2"; shift 2; exec "$@"' \
  bash "$bashrc" "$extra" "$@"
