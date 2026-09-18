#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pickle
import re
from pathlib import Path


VISCOELASTIC_MODELS = (
    "Oldroyd", "FENE", "Giesekus", "PTT", "PomPom", "Rolie", "Saramito",
)
GNF_MODELS = ("Carreau", "Herschel", "BirdCarreau", "CrossPowerLaw", "powerLaw")


def inferred_metadata(metadata: dict) -> dict:
    solver = str(metadata.get("case_solver") or "")
    content = str(metadata.get("full_content") or "")
    models = sorted(set(re.findall(r"\btype\s+([A-Za-z0-9_.+-]+)\s*;", content)))
    if any(any(token in model for token in VISCOELASTIC_MODELS) for model in models):
        family = "viscoelastic"
    elif any(any(token in model for token in GNF_MODELS) for model in models):
        family = "generalized-newtonian"
    else:
        family = "newtonian"

    two_phase = solver in {"interFoam", "rheoInterFoam"}
    if solver == "rheoTestFoam":
        objective = "material-functions"
        flow_regime = "material-test"
    elif two_phase:
        objective = "free-surface"
        flow_regime = "transient"
    elif solver == "simpleFoam":
        objective = "flow-field"
        flow_regime = "steady"
    else:
        objective = "flow-field"
        flow_regime = "transient"

    return {
        "solver": solver,
        "constitutive_family": family,
        "model": ",".join(models) if models else "Newtonian",
        "phase_type": "two-phase" if two_phase else "single-phase",
        "geometry_family": str(metadata.get("case_category") or "unspecified"),
        "flow_regime": flow_regime,
        "objective": objective,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Add physics metadata to tutorial FAISS docstores")
    parser.add_argument("--database", type=Path, default=Path("database"))
    args = parser.parse_args()
    paths = []
    for channel in ("v9-rheotool", "v10-foundation"):
        for index in (
            "openfoam_allrun_scripts", "openfoam_tutorials_structure",
            "openfoam_tutorials_details",
        ):
            paths.extend((args.database / channel / "faiss").glob(f"*/{index}/index.pkl"))

    for path in sorted(paths):
        with path.open("rb") as stream:
            docstore, mapping = pickle.load(stream)
        for document in docstore._dict.values():
            document.metadata.update(inferred_metadata(document.metadata))
        with path.open("wb") as stream:
            pickle.dump((docstore, mapping), stream)
        print(f"Enriched {len(docstore._dict)} documents: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
