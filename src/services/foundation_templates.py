from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from utils import read_case_foamfiles, scan_case_directory


DEFAULT_OPENFOAM10_TUTORIAL_ROOT = Path("/opt/openfoam10/tutorials")

FOUNDATION_TEMPLATE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "foundation_v10_icofoam_cavity": {
        "solver": "icoFoam",
        "relative_source": "incompressible/icoFoam/cavity/cavity",
        "case_name": "foundation-v10-icofoam-cavity",
        "case_domain": "incompressible",
        "case_category": "foundation_tutorial_icofoam_cavity",
        "template_name": "OpenFOAM v10 icoFoam/cavity",
        "matched_alias": "OpenFOAM v10 incompressible/icoFoam/cavity/cavity",
        "required_files": (
            "0/U", "0/p", "constant/physicalProperties",
            "system/blockMeshDict", "system/controlDict", "system/fvSchemes", "system/fvSolution",
        ),
        "allrun_steps": ("blockMesh", "checkMesh", "$(getApplication)"),
    },
    "foundation_v10_icofoam_cavity_full_allrun": {
        "solver": "icoFoam",
        "relative_source": "incompressible/icoFoam/cavity",
        "case_name": "foundation-v10-icofoam-cavity-full-allrun",
        "case_domain": "incompressible",
        "case_category": "foundation_tutorial_icofoam_cavity_family",
        "template_name": "OpenFOAM v10 icoFoam/cavity full tutorial family",
        "matched_alias": "OpenFOAM v10 incompressible/icoFoam/cavity parent Allrun",
        "multi_case": True,
        "subcases": ("cavity", "cavityFine", "cavityGrade", "cavityHighRe", "cavityClipped"),
        "required_files": (
            "Allrun",
            "cavity/0/U",
            "cavity/0/p",
            "cavity/constant/physicalProperties",
            "cavity/system/blockMeshDict",
            "cavity/system/controlDict",
            "cavity/system/fvSchemes",
            "cavity/system/fvSolution",
            "cavityGrade/0/U",
            "cavityGrade/0/p",
            "cavityGrade/constant/physicalProperties",
            "cavityGrade/system/blockMeshDict",
            "cavityGrade/system/controlDict",
            "cavityGrade/system/fvSchemes",
            "cavityGrade/system/fvSolution",
            "cavityClipped/0/U",
            "cavityClipped/0/p",
            "cavityClipped/constant/physicalProperties",
            "cavityClipped/system/blockMeshDict",
            "cavityClipped/system/controlDict",
            "cavityClipped/system/fvSchemes",
            "cavityClipped/system/fvSolution",
        ),
    },
    "foundation_v10_simplefoam_pitzdaily": {
        "solver": "simpleFoam",
        "relative_source": "incompressible/simpleFoam/pitzDaily",
        "case_name": "foundation-v10-simplefoam-pitzdaily",
        "case_domain": "incompressible",
        "case_category": "foundation_tutorial_simplefoam_pitzdaily",
        "template_name": "OpenFOAM v10 simpleFoam/pitzDaily",
        "matched_alias": "OpenFOAM v10 incompressible/simpleFoam/pitzDaily",
        "required_files": (
            "0/U", "0/p", "constant/momentumTransport", "constant/physicalProperties",
            "system/controlDict", "system/fvSchemes", "system/fvSolution",
        ),
        "allrun_steps": (
            "blockMesh -dict $FOAM_TUTORIALS/resources/blockMesh/pitzDaily",
            "checkMesh",
            "$(getApplication)",
        ),
    },
    "foundation_v10_pimplefoam_ras_pitzdaily": {
        "solver": "pimpleFoam",
        "relative_source": "incompressible/pimpleFoam/RAS/pitzDaily",
        "case_name": "foundation-v10-pimplefoam-ras-pitzdaily",
        "case_domain": "incompressible",
        "case_category": "foundation_tutorial_pimplefoam_ras_pitzdaily",
        "template_name": "OpenFOAM v10 pimpleFoam/RAS/pitzDaily",
        "matched_alias": "OpenFOAM v10 incompressible/pimpleFoam/RAS/pitzDaily",
        "required_files": (
            "0/U", "0/p", "0/k", "0/epsilon", "0/nut",
            "constant/momentumTransport", "constant/physicalProperties",
            "system/controlDict", "system/fvSchemes", "system/fvSolution",
        ),
        "allrun_steps": (
            "blockMesh -dict $FOAM_TUTORIALS/resources/blockMesh/pitzDaily",
            "checkMesh",
            "$(getApplication)",
        ),
    },
    "foundation_v10_pisofoam_les_pitzdaily": {
        "solver": "pisoFoam",
        "relative_source": "incompressible/pisoFoam/LES/pitzDaily",
        "case_name": "foundation-v10-pisofoam-les-pitzdaily",
        "case_domain": "incompressible",
        "case_category": "foundation_tutorial_pisofoam_les_pitzdaily",
        "template_name": "OpenFOAM v10 pisoFoam/LES/pitzDaily",
        "matched_alias": "OpenFOAM v10 incompressible/pisoFoam/LES/pitzDaily",
        "required_files": (
            "0/U", "0/p", "0/k", "0/nut",
            "constant/momentumTransport", "constant/physicalProperties",
            "system/controlDict", "system/fvSchemes", "system/fvSolution",
        ),
        "allrun_steps": (
            "blockMesh -dict $FOAM_TUTORIALS/resources/blockMesh/pitzDaily",
            "checkMesh",
            "$(getApplication)",
        ),
    },
    "foundation_v10_potentialfoam_pitzdaily": {
        "solver": "potentialFoam",
        "relative_source": "basic/potentialFoam/pitzDaily",
        "case_name": "foundation-v10-potentialfoam-pitzdaily",
        "case_domain": "basic",
        "case_category": "foundation_tutorial_potentialfoam_pitzdaily",
        "template_name": "OpenFOAM v10 potentialFoam/pitzDaily",
        "matched_alias": "OpenFOAM v10 basic/potentialFoam/pitzDaily",
        "required_files": (
            "0/U.orig", "0/p.orig",
            "system/controlDict", "system/fvSchemes", "system/fvSolution",
        ),
        "allrun_steps": (
            "blockMesh -dict $FOAM_TUTORIALS/resources/blockMesh/pitzDaily",
            "checkMesh",
            "$(getApplication) -writePhi -writep",
            "postProcess -func streamFunction",
        ),
    },
    "foundation_v10_scalartransport_pitzdaily": {
        "solver": "scalarTransportFoam",
        "relative_source": "basic/scalarTransportFoam/pitzDaily",
        "case_name": "foundation-v10-scalartransport-pitzdaily",
        "case_domain": "basic",
        "case_category": "foundation_tutorial_scalartransport_pitzdaily",
        "template_name": "OpenFOAM v10 scalarTransportFoam/pitzDaily",
        "matched_alias": "OpenFOAM v10 basic/scalarTransportFoam/pitzDaily",
        "required_files": (
            "0/T", "0/U", "constant/physicalProperties",
            "system/controlDict", "system/fvSchemes", "system/fvSolution",
        ),
        "allrun_steps": (
            "blockMesh -dict $FOAM_TUTORIALS/resources/blockMesh/pitzDaily",
            "checkMesh",
            "$(getApplication)",
        ),
    },
    "foundation_v10_potentialfoam_cylinder": {
        "solver": "potentialFoam",
        "relative_source": "basic/potentialFoam/cylinder",
        "case_name": "foundation-v10-potentialfoam-cylinder",
        "case_domain": "basic",
        "case_category": "foundation_tutorial_potentialfoam_cylinder",
        "template_name": "OpenFOAM v10 potentialFoam/cylinder",
        "matched_alias": "OpenFOAM v10 basic/potentialFoam/cylinder",
        "required_files": (
            "0/U.orig", "0/p.orig", "system/blockMeshDict",
            "system/controlDict", "system/fvSchemes", "system/fvSolution",
        ),
        "allrun_steps": (
            "blockMesh",
            "checkMesh",
            "$(getApplication) -withFunctionObjects -writePhi -writep",
            "postProcess -func streamFunction",
        ),
    },
    "foundation_v10_pimplefoam_laminar_offsetcylinder": {
        "solver": "pimpleFoam",
        "relative_source": "incompressible/pimpleFoam/laminar/offsetCylinder",
        "case_name": "foundation-v10-pimplefoam-laminar-offsetcylinder",
        "case_domain": "incompressible",
        "case_category": "foundation_tutorial_pimplefoam_laminar_offsetcylinder",
        "template_name": "OpenFOAM v10 pimpleFoam/laminar/offsetCylinder",
        "matched_alias": "OpenFOAM v10 incompressible/pimpleFoam/laminar/offsetCylinder",
        "required_files": (
            "0/U", "0/p", "constant/momentumTransport", "constant/physicalProperties",
            "system/blockMeshDict", "system/controlDict", "system/fvSchemes", "system/fvSolution",
        ),
        "allrun_steps": ("blockMesh", "checkMesh", "$(getApplication)"),
    },
    "foundation_v10_interfoam_laminar_sloshingcylinder": {
        "solver": "interFoam",
        "relative_source": "multiphase/interFoam/laminar/sloshingCylinder",
        "case_name": "foundation-v10-interfoam-laminar-sloshingcylinder",
        "case_domain": "multiphase",
        "case_category": "foundation_tutorial_interfoam_laminar_sloshingcylinder",
        "template_name": "OpenFOAM v10 interFoam/laminar/sloshingCylinder",
        "matched_alias": "OpenFOAM v10 multiphase/interFoam/laminar/sloshingCylinder",
        "required_files": (
            "0/U", "0/p_rgh", "0/alpha.water.orig",
            "constant/dynamicMeshDict", "constant/g", "constant/momentumTransport",
            "constant/phaseProperties", "system/blockMeshDict", "system/controlDict",
            "system/fvSchemes", "system/fvSolution", "system/meshQualityDict",
            "system/setFieldsDict", "system/snappyHexMeshDict",
        ),
        "allrun_steps": (
            "blockMesh",
            "snappyHexMesh -overwrite",
            "checkMesh",
            "setFields",
            "$(getApplication)",
        ),
    },
    "foundation_v10_rhocentralfoam_forwardstep": {
        "solver": "rhoCentralFoam",
        "relative_source": "compressible/rhoCentralFoam/forwardStep",
        "case_name": "foundation-v10-rhocentralfoam-forwardstep",
        "case_domain": "compressible",
        "case_category": "foundation_tutorial_rhocentralfoam_forwardstep",
        "template_name": "OpenFOAM v10 rhoCentralFoam/forwardStep",
        "matched_alias": "OpenFOAM v10 compressible/rhoCentralFoam/forwardStep",
        "required_files": (
            "0/U", "0/p", "0/T", "constant/momentumTransport", "constant/physicalProperties",
            "system/blockMeshDict", "system/controlDict", "system/fvSchemes", "system/fvSolution",
        ),
        "allrun_steps": ("blockMesh", "checkMesh", "$(getApplication)"),
    },
    "foundation_v10_rhopimplefoam_laminar_forwardstep": {
        "solver": "rhoPimpleFoam",
        "relative_source": "compressible/rhoPimpleFoam/laminar/forwardStep",
        "case_name": "foundation-v10-rhopimplefoam-laminar-forwardstep",
        "case_domain": "compressible",
        "case_category": "foundation_tutorial_rhopimplefoam_laminar_forwardstep",
        "template_name": "OpenFOAM v10 rhoPimpleFoam/laminar/forwardStep",
        "matched_alias": "OpenFOAM v10 compressible/rhoPimpleFoam/laminar/forwardStep",
        "required_files": (
            "0/U", "0/p", "0/T", "constant/momentumTransport", "constant/physicalProperties",
            "system/blockMeshDict", "system/controlDict", "system/fvSchemes", "system/fvSolution",
        ),
        "allrun_steps": ("blockMesh", "checkMesh", "$(getApplication)"),
    },
    "foundation_v10_buoyantfoam_bernardcells": {
        "solver": "buoyantFoam",
        "relative_source": "heatTransfer/buoyantFoam/BernardCells",
        "case_name": "foundation-v10-buoyantfoam-bernardcells",
        "case_domain": "heatTransfer",
        "case_category": "foundation_tutorial_buoyantfoam_bernardcells",
        "template_name": "OpenFOAM v10 buoyantFoam/BernardCells",
        "matched_alias": "OpenFOAM v10 heatTransfer/buoyantFoam/BernardCells",
        "required_files": (
            "0/U", "0/p", "0/p_rgh", "0/T", "0/alphat",
            "0/epsilon", "0/k", "0/nut", "constant/g",
            "constant/momentumTransport", "constant/physicalProperties",
            "system/blockMeshDict", "system/controlDict", "system/fvSchemes", "system/fvSolution",
        ),
        "allrun_steps": ("blockMesh", "checkMesh", "$(getApplication)"),
    },
    "foundation_v10_pimplefoam_laminar_planarpoiseuille": {
        "solver": "pimpleFoam",
        "relative_source": "incompressible/pimpleFoam/laminar/planarPoiseuille",
        "case_name": "foundation-v10-pimplefoam-laminar-planarpoiseuille",
        "case_domain": "incompressible",
        "case_category": "foundation_tutorial_pimplefoam_laminar_planarpoiseuille",
        "template_name": "OpenFOAM v10 pimpleFoam/laminar/planarPoiseuille",
        "matched_alias": "OpenFOAM v10 incompressible/pimpleFoam/laminar/planarPoiseuille",
        "required_files": (
            "0/U", "0/p", "0/sigma", "constant/fvModels",
            "constant/momentumTransport", "constant/physicalProperties",
            "system/blockMeshDict", "system/controlDict", "system/fvSchemes", "system/fvSolution",
        ),
        "allrun_steps": ("blockMesh", "checkMesh", "$(getApplication)"),
    },
    "foundation_v10_rhocentralfoam_obliqueshock": {
        "solver": "rhoCentralFoam",
        "relative_source": "compressible/rhoCentralFoam/obliqueShock",
        "case_name": "foundation-v10-rhocentralfoam-obliqueshock",
        "case_domain": "compressible",
        "case_category": "foundation_tutorial_rhocentralfoam_obliqueshock",
        "template_name": "OpenFOAM v10 rhoCentralFoam/obliqueShock",
        "matched_alias": "OpenFOAM v10 compressible/rhoCentralFoam/obliqueShock",
        "required_files": (
            "0/U", "0/p", "0/T", "constant/momentumTransport", "constant/physicalProperties",
            "system/blockMeshDict", "system/controlDict", "system/fvSchemes", "system/fvSolution",
        ),
        "allrun_steps": ("blockMesh", "checkMesh", "$(getApplication)"),
    },
    "foundation_v10_rhocentralfoam_shocktube": {
        "solver": "rhoCentralFoam",
        "relative_source": "compressible/rhoCentralFoam/shockTube",
        "case_name": "foundation-v10-rhocentralfoam-shocktube",
        "case_domain": "compressible",
        "case_category": "foundation_tutorial_rhocentralfoam_shocktube",
        "template_name": "OpenFOAM v10 rhoCentralFoam/shockTube",
        "matched_alias": "OpenFOAM v10 compressible/rhoCentralFoam/shockTube",
        "required_files": (
            "0/U.orig", "0/p.orig", "0/T.orig", "constant/momentumTransport", "constant/physicalProperties",
            "system/blockMeshDict", "system/controlDict", "system/fvSchemes", "system/fvSolution",
            "system/setFieldsDict", "system/sample",
        ),
        "allrun_steps": ("blockMesh", "checkMesh", "setFields", "$(getApplication)", "-s sample postProcess -func sample"),
    },
    "foundation_v10_rhopimplefoam_laminar_shocktube": {
        "solver": "rhoPimpleFoam",
        "relative_source": "compressible/rhoPimpleFoam/laminar/shockTube",
        "case_name": "foundation-v10-rhopimplefoam-laminar-shocktube",
        "case_domain": "compressible",
        "case_category": "foundation_tutorial_rhopimplefoam_laminar_shocktube",
        "template_name": "OpenFOAM v10 rhoPimpleFoam/laminar/shockTube",
        "matched_alias": "OpenFOAM v10 compressible/rhoPimpleFoam/laminar/shockTube",
        "required_files": (
            "0/U.orig", "0/p.orig", "0/T.orig", "constant/momentumTransport", "constant/physicalProperties",
            "system/blockMeshDict", "system/controlDict", "system/fvSchemes", "system/fvSolution",
            "system/setFieldsDict", "system/sample",
        ),
        "allrun_steps": ("blockMesh", "checkMesh", "setFields", "$(getApplication)", "-s sample postProcess -func sample"),
    },
    "foundation_v10_simplefoam_airfoil2d": {
        "solver": "simpleFoam",
        "relative_source": "incompressible/simpleFoam/airFoil2D",
        "case_name": "foundation-v10-simplefoam-airfoil2d",
        "case_domain": "incompressible",
        "case_category": "foundation_tutorial_simplefoam_airfoil2d",
        "template_name": "OpenFOAM v10 simpleFoam/airFoil2D",
        "matched_alias": "OpenFOAM v10 incompressible/simpleFoam/airFoil2D",
        "required_files": (
            "0/U", "0/p", "0/nut", "0/nuTilda", "constant/momentumTransport",
            "constant/physicalProperties", "constant/polyMesh/points", "system/controlDict",
            "system/fvSchemes", "system/fvSolution",
        ),
        "allrun_steps": ("$(getApplication)",),
    },
    "foundation_v10_interfoam_laminar_capillaryrise": {
        "solver": "interFoam",
        "relative_source": "multiphase/interFoam/laminar/capillaryRise",
        "case_name": "foundation-v10-interfoam-laminar-capillaryrise",
        "case_domain": "multiphase",
        "case_category": "foundation_tutorial_interfoam_laminar_capillaryrise",
        "template_name": "OpenFOAM v10 interFoam/laminar/capillaryRise",
        "matched_alias": "OpenFOAM v10 multiphase/interFoam/laminar/capillaryRise",
        "required_files": (
            "0/U", "0/p_rgh", "0/alpha.water.orig", "constant/g",
            "constant/momentumTransport", "constant/phaseProperties", "system/blockMeshDict",
            "system/controlDict", "system/fvSchemes", "system/fvSolution", "system/setFieldsDict",
        ),
        "allrun_steps": ("blockMesh", "checkMesh", "setFields", "$(getApplication)"),
    },
    "foundation_v10_interfoam_laminar_wave": {
        "solver": "interFoam",
        "relative_source": "multiphase/interFoam/laminar/wave",
        "case_name": "foundation-v10-interfoam-laminar-wave",
        "case_domain": "multiphase",
        "case_category": "foundation_tutorial_interfoam_laminar_wave",
        "template_name": "OpenFOAM v10 interFoam/laminar/wave",
        "matched_alias": "OpenFOAM v10 multiphase/interFoam/laminar/wave",
        "required_files": (
            "0/U.orig", "0/p_rgh", "0/alpha.water.orig", "constant/fvModels",
            "constant/g", "constant/momentumTransport", "constant/phaseProperties",
            "constant/waveProperties", "system/blockMeshDict", "system/controlDict",
            "system/decomposeParDict", "system/extrudeMeshDict", "system/fvSchemes",
            "system/fvSolution", "system/setWavesDict",
        ),
        "allrun_raw_body": """runApplication blockMesh
runApplication extrudeMesh

for i in 1 2
do
    runApplication -s $i topoSet -dict topoSetDict$i
    runApplication -s $i refineMesh -dict refineMeshDictX -overwrite
done

for i in 3 4 5 6
do
    runApplication -s $i topoSet -dict topoSetDict$i
    runApplication -s $i refineMesh -dict refineMeshDictY -overwrite
done

runApplication setWaves
runApplication decomposePar
runParallel $(getApplication)
runApplication reconstructPar""",
    },
    "foundation_v10_interfoam_dambreak": {
        "solver": "interFoam",
        "relative_source": "multiphase/interFoam/laminar/damBreak/damBreak",
        "case_name": "foundation-v10-interfoam-dambreak",
        "case_domain": "multiphase",
        "case_category": "foundation_tutorial_interfoam_dambreak",
        "template_name": "OpenFOAM v10 interFoam/laminar/damBreak",
        "matched_alias": "OpenFOAM v10 multiphase/interFoam/laminar/damBreak/damBreak",
        "required_files": (
            "0/U", "0/p_rgh", "0/alpha.water.orig",
            "constant/g", "constant/momentumTransport", "constant/phaseProperties",
            "system/blockMeshDict", "system/controlDict", "system/fvSchemes",
            "system/fvSolution", "system/setFieldsDict",
        ),
        "allrun_steps": ("blockMesh", "checkMesh", "setFields", "$(getApplication)"),
    },
    "foundation_v10_interfoam_dambreak_laminar_full_allrun": {
        "solver": "interFoam",
        "relative_source": "multiphase/interFoam/laminar/damBreak",
        "case_name": "foundation-v10-interfoam-dambreak-laminar-full-allrun",
        "case_domain": "multiphase",
        "case_category": "foundation_tutorial_interfoam_dambreak_family",
        "template_name": "OpenFOAM v10 interFoam/laminar/damBreak full tutorial family",
        "matched_alias": "OpenFOAM v10 multiphase/interFoam/laminar/damBreak parent Allrun",
        "multi_case": True,
        "subcases": ("damBreak", "damBreakFine"),
        "required_files": (
            "Allrun",
            "damBreak/0/U", "damBreak/0/p_rgh", "damBreak/0/alpha.water.orig",
            "damBreak/constant/g", "damBreak/constant/momentumTransport",
            "damBreak/constant/phaseProperties", "damBreak/system/blockMeshDict",
            "damBreak/system/controlDict", "damBreak/system/fvSchemes",
            "damBreak/system/fvSolution", "damBreak/system/setFieldsDict",
        ),
    },
    "foundation_v10_interfoam_dambreak_with_obstacle": {
        "solver": "interFoam",
        "relative_source": "multiphase/interFoam/laminar/damBreakWithObstacle",
        "case_name": "foundation-v10-interfoam-dambreak-with-obstacle",
        "case_domain": "multiphase",
        "case_category": "foundation_tutorial_interfoam_dambreak_with_obstacle",
        "template_name": "OpenFOAM v10 interFoam/laminar/damBreakWithObstacle",
        "matched_alias": "OpenFOAM v10 multiphase/interFoam/laminar/damBreakWithObstacle",
        "required_files": (
            "0/U.orig", "0/p_rgh", "0/alpha.water.orig",
            "constant/g", "constant/dynamicMeshDict", "constant/momentumTransport",
            "constant/phaseProperties", "system/blockMeshDict", "system/controlDict",
            "system/fvSchemes", "system/fvSolution", "system/setFieldsDict", "system/topoSetDict",
        ),
        "allrun_steps": (
            "blockMesh",
            "checkMesh",
            "topoSet",
            "subsetMesh -overwrite c0 -patch walls -noFields",
            "setFields",
            "$(getApplication)",
        ),
    },
    "foundation_v10_interfoam_ras_dambreak": {
        "solver": "interFoam",
        "relative_source": "multiphase/interFoam/RAS/damBreak/damBreak",
        "case_name": "foundation-v10-interfoam-ras-dambreak",
        "case_domain": "multiphase",
        "case_category": "foundation_tutorial_interfoam_ras_dambreak",
        "template_name": "OpenFOAM v10 interFoam/RAS/damBreak",
        "matched_alias": "OpenFOAM v10 multiphase/interFoam/RAS/damBreak/damBreak",
        "required_files": (
            "0/U", "0/p_rgh", "0/alpha.water.orig", "0/k", "0/epsilon", "0/nut",
            "constant/g", "constant/fvModels", "constant/momentumTransport",
            "constant/phaseProperties", "system/blockMeshDict", "system/controlDict",
            "system/fvSchemes", "system/fvSolution", "system/setFieldsDict",
        ),
        "allrun_steps": ("blockMesh", "checkMesh", "setFields", "$(getApplication)"),
    },
    "foundation_v10_interfoam_ras_dambreak_full_allrun": {
        "solver": "interFoam",
        "relative_source": "multiphase/interFoam/RAS/damBreak",
        "case_name": "foundation-v10-interfoam-ras-dambreak-full-allrun",
        "case_domain": "multiphase",
        "case_category": "foundation_tutorial_interfoam_ras_dambreak_family",
        "template_name": "OpenFOAM v10 interFoam/RAS/damBreak full tutorial family",
        "matched_alias": "OpenFOAM v10 multiphase/interFoam/RAS/damBreak parent Allrun",
        "multi_case": True,
        "subcases": ("damBreak", "damBreakFine"),
        "required_files": (
            "Allrun",
            "damBreak/0/U", "damBreak/0/p_rgh", "damBreak/0/alpha.water.orig",
            "damBreak/0/k", "damBreak/0/epsilon", "damBreak/0/nut",
            "damBreak/constant/g", "damBreak/constant/fvModels",
            "damBreak/constant/momentumTransport", "damBreak/constant/phaseProperties",
            "damBreak/system/blockMeshDict", "damBreak/system/controlDict",
            "damBreak/system/fvSchemes", "damBreak/system/fvSolution",
            "damBreak/system/setFieldsDict",
        ),
    },
    "foundation_v10_interfoam_ras_dambreak_porous_baffle": {
        "solver": "interFoam",
        "relative_source": "multiphase/interFoam/RAS/damBreakPorousBaffle",
        "case_name": "foundation-v10-interfoam-ras-dambreak-porous-baffle",
        "case_domain": "multiphase",
        "case_category": "foundation_tutorial_interfoam_ras_dambreak_porous_baffle",
        "template_name": "OpenFOAM v10 interFoam/RAS/damBreakPorousBaffle",
        "matched_alias": "OpenFOAM v10 multiphase/interFoam/RAS/damBreakPorousBaffle",
        "required_files": (
            "0/U.orig", "0/p_rgh.orig", "0/alpha.water.orig",
            "0/k.orig", "0/epsilon.orig", "0/nut.orig",
            "constant/g", "constant/momentumTransport", "constant/phaseProperties",
            "system/blockMeshDict", "system/controlDict", "system/createBafflesDict",
            "system/fvSchemes", "system/fvSolution", "system/setFieldsDict",
        ),
        "allrun_steps": (
            "blockMesh",
            "checkMesh",
            "setFields",
            "createBaffles -overwrite",
            "$(getApplication)",
        ),
    },
}


def _copy_case_tree(source_dir: Path, destination_dir: Path) -> None:
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Foundation tutorial template not found: {source_dir}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    for item in source_dir.iterdir():
        destination = destination_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


def _is_executable_foundation_case(source_dir: Path, template_match: dict[str, Any]) -> bool:
    required = FOUNDATION_TEMPLATE_DEFINITIONS[template_match["id"]]["required_files"]
    return all((source_dir / rel_path).is_file() for rel_path in required)


def _write_single_case_allrun(destination_dir: Path, template_match: dict[str, Any]) -> None:
    definition = FOUNDATION_TEMPLATE_DEFINITIONS[template_match["id"]]
    steps = definition.get("allrun_raw_body")
    if not steps:
        steps = "\n".join(
            f"runApplication {step}"
            for step in definition["allrun_steps"]
        )
    allrun = f"""#!/bin/sh
cd ${{0%/*}} || exit 1

. $WM_PROJECT_DIR/bin/tools/RunFunctions

{steps}

#------------------------------------------------------------------------------
"""
    path = destination_dir / "Allrun"
    path.write_text(allrun, encoding="utf-8")
    path.chmod(0o755)


def is_foundation_multi_case_template(case_dir: str | Path) -> bool:
    note_path = Path(case_dir) / "TUTORIAL_TEMPLATE_IMPORT.json"
    if not note_path.is_file():
        return False
    try:
        note = json.loads(note_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return bool(note.get("multi_case"))


def summarize_foundation_multi_case(case_dir: str | Path) -> dict[str, Any] | None:
    case_path = Path(case_dir)
    note_path = case_path / "TUTORIAL_TEMPLATE_IMPORT.json"
    if not note_path.is_file():
        return None
    try:
        note = json.loads(note_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not note.get("multi_case"):
        return None

    subcases = note.get("subcases") or ()
    solver = str(note.get("solver") or "icoFoam")
    rows = []
    for name in subcases:
        subcase = case_path / str(name)
        times: list[float] = []
        if subcase.is_dir():
            for child in subcase.iterdir():
                if not child.is_dir():
                    continue
                try:
                    times.append(float(child.name))
                except ValueError:
                    pass
        final_time = max(times) if times else None

        solver_log = subcase / f"log.{solver}"
        solver_completed = False
        if solver_log.is_file():
            solver_completed = bool(
                any(line.strip() == "End" for line in solver_log.read_text(encoding="utf-8", errors="ignore").splitlines())
            )

        map_fields_log = subcase / "log.mapFields"
        map_fields = "not_applicable"
        if map_fields_log.is_file():
            map_fields = "passed" if any(
                line.strip() == "End"
                for line in map_fields_log.read_text(encoding="utf-8", errors="ignore").splitlines()
            ) else "failed"

        rows.append({
            "name": str(name),
            "exists": subcase.is_dir(),
            "final_time": final_time,
            "solver_log": str(solver_log.relative_to(case_path)) if solver_log.is_file() else None,
            "solver_completed": solver_completed,
            "mapFields": map_fields,
            "mapFields_log": str(map_fields_log.relative_to(case_path)) if map_fields_log.is_file() else None,
        })

    summary = {
        "template_id": note.get("template_id"),
        "multi_case": True,
        "subcases": rows,
        "all_passed": all(row["exists"] and row["solver_completed"] for row in rows),
    }
    (case_path / "FOUNDATION_MULTI_CASE_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def find_foundation_tutorial_template(
    user_requirement: str,
    case_target: Any,
    *,
    compiled_workflow: Any | None = None,
    template_root: Path | None = None,
) -> dict[str, Any] | None:
    if template_root is None:
        template_root = Path(
            os.getenv("FOAMAGENT_OPENFOAM10_TUTORIAL_ROOT", str(DEFAULT_OPENFOAM10_TUTORIAL_ROOT))
        )
    template_id = getattr(getattr(compiled_workflow, "intent", None), "reproduction_target", None)
    if template_id not in FOUNDATION_TEMPLATE_DEFINITIONS:
        return None
    definition = FOUNDATION_TEMPLATE_DEFINITIONS[template_id]
    if getattr(case_target, "solver", None) != definition["solver"]:
        return None

    source_dir = template_root / definition["relative_source"]
    return {
        "id": template_id,
        "template_id": template_id,
        "template_kind": "foundation",
        "solver": definition["solver"],
        "source_dir": str(source_dir),
        "case_name": definition["case_name"],
        "case_domain": definition["case_domain"],
        "case_category": definition["case_category"],
        "template_name": definition["template_name"],
        "matched_alias": definition["matched_alias"],
        "import_policy": "foundation tutorial template import; no LLM dictionary regeneration",
        "match_score": 100,
        "match_reasons": [f"reproduction_target={template_id}"],
        "tier": "A",
        "rag_confidence": "high",
        "multi_case": bool(definition.get("multi_case")),
    }


def foundation_template_subtasks(template_match: dict[str, Any]) -> list[dict[str, str]]:
    source_dir = Path(template_match["source_dir"])
    subtasks: list[dict[str, str]] = []
    if not source_dir.is_dir():
        return subtasks
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source_dir)
        if len(rel.parts) == 1:
            folder_name = ""
            file_name = rel.parts[0]
        else:
            folder_name = str(Path(*rel.parts[:-1]))
            file_name = rel.parts[-1]
        subtasks.append({"folder_name": folder_name, "file_name": file_name})
    subtasks.append({"folder_name": "", "file_name": "Allrun"})
    return subtasks


def import_foundation_tutorial_template(
    case_dir: str,
    template_match: dict[str, Any],
    user_requirement: str = "",
) -> dict[str, Any]:
    source_dir = Path(template_match["source_dir"])
    destination_dir = Path(case_dir)
    if not _is_executable_foundation_case(source_dir, template_match):
        raise ValueError(
            "FOUNDATION_TEMPLATE_NOT_EXECUTABLE: "
            f"{template_match.get('id')} source directory is not a runnable single OpenFOAM case: {source_dir}"
        )

    _copy_case_tree(source_dir, destination_dir)
    if not template_match.get("multi_case"):
        _write_single_case_allrun(destination_dir, template_match)

    note = {
        "template_id": template_match["id"],
        "template_name": template_match.get("template_name"),
        "solver": template_match.get("solver"),
        "source_directory": str(source_dir),
        "matched_alias": template_match.get("matched_alias"),
        "import_policy": template_match.get("import_policy"),
        "tier": template_match.get("tier"),
        "rag_confidence": template_match.get("rag_confidence"),
        "match_score": template_match.get("match_score"),
        "match_reasons": template_match.get("match_reasons"),
    }
    definition = FOUNDATION_TEMPLATE_DEFINITIONS[template_match["id"]]
    if definition.get("multi_case"):
        note["multi_case"] = True
        note["subcases"] = list(definition.get("subcases", ()))
    (destination_dir / "TUTORIAL_TEMPLATE_IMPORT.json").write_text(
        json.dumps(note, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    dir_structure = scan_case_directory(str(destination_dir))
    foamfiles = read_case_foamfiles(str(destination_dir), dir_structure)
    return {
        "dir_structure": dir_structure,
        "foamfiles": foamfiles,
        "tutorial_template_import": note,
    }
