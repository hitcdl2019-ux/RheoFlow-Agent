#!/usr/bin/env bash
set -euo pipefail

IMAGE=${IMAGE:-foamagent-dual-openfoam@sha256:c15f3b22d2bcc648b95ae0e2ef929bfb88723eb901b51de4e1b2719945650e5d}
ARTIFACT_DIR=${ARTIFACT_DIR:-runs/dual-channel-regression}
mkdir -p "$ARTIFACT_DIR"

docker run --rm --user openfoam --entrypoint /bin/bash "$IMAGE" -lc '
set -euo pipefail

runner=/home/openfoam/Foam-Agent/scripts/run_openfoam_channel.sh
work=$(mktemp -d)
trap '\''rm -rf "$work"'\'' EXIT

run_case() {
    name=$1 channel=$2 source=$3 end_time=$4
    shift 4
    case_dir="$work/$name"
    cp -a "$source" "$case_dir"
    cd "$case_dir"

    sed -Ei "s/^([[:space:]]*endTime[[:space:]]+)[^;]+;/\\1${end_time};/" system/controlDict

    for command in "$@"; do
        read -r -a args <<< "$command"
        if ! "$runner" "$channel" "${args[@]}" >> "log.$name" 2>&1; then
            tail -80 "log.$name"
            return 1
        fi
    done

    if ! grep -q "^End$" "log.$name" || grep -q "FOAM FATAL" "log.$name"; then
        tail -80 "log.$name"
        return 1
    fi
    printf "PASS %-14s channel=%s endTime=%s\\n" "$name" "$channel" "$end_time"
}

run_case rheoFoam v9-rheotool \
    /opt/build/rheoTool/of90/tutorials/rheoFoam/Cavity/Oldroyd-BLog 0.002 \
    blockMesh rheoFoam "postProcess -func sampleDict"

run_case rheoTestFoam v9-rheotool \
    /opt/build/rheoTool/of90/tutorials/rheoTestFoam/FENE-CR 0.01 \
    blockMesh rheoTestFoam

# The tutorial Allrun performs this initial-field copy before setFields.
source=/opt/build/rheoTool/of90/tutorials/rheoInterFoam/damBreak/Newtonian
case_dir="$work/rheoInterFoam"
cp -a "$source" "$case_dir"
cd "$case_dir"
sed -Ei "s/^([[:space:]]*endTime[[:space:]]+)[^;]+;/\\1 0.001;/" system/controlDict
cp 0/alpha.water.org 0/alpha.water
for command in blockMesh setFields rheoInterFoam; do
    if ! "$runner" v9-rheotool "$command" >> log.rheoInterFoam 2>&1; then
        tail -80 log.rheoInterFoam
        exit 1
    fi
done
if ! grep -q "^End$" log.rheoInterFoam || grep -q "FOAM FATAL" log.rheoInterFoam; then
    tail -80 log.rheoInterFoam
    exit 1
fi
printf "PASS %-14s channel=%s endTime=%s\\n" rheoInterFoam v9-rheotool 0.001

run_case icoFoam v10-foundation \
    /opt/openfoam10/tutorials/incompressible/icoFoam/cavity/cavity 0.01 \
    blockMesh icoFoam

run_case simpleFoam v10-foundation \
    /opt/openfoam10/tutorials/incompressible/simpleFoam/pitzDaily 5 \
    "blockMesh -dict /opt/openfoam10/tutorials/resources/blockMesh/pitzDaily" simpleFoam

run_case pimpleFoam v10-foundation \
    /opt/openfoam10/tutorials/incompressible/pimpleFoam/laminar/planarCouette 0.02 \
    blockMesh pimpleFoam

run_case interFoam v10-foundation \
    /opt/openfoam10/tutorials/multiphase/interFoam/laminar/damBreak/damBreak 0.005 \
    blockMesh setFields interFoam
' 2>&1 | tee "$ARTIFACT_DIR/regression.log"
