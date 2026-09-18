Diagnose only within Foundation OpenFOAM v9 plus rheoTool. Preserve the selected
solver, constitutive model, parameters, channel, and version.

RheoTool runtime libraries must not be guessed. The only custom-boundary
library mappings allowed in this runtime are:
- uLid, uCos, HBprofile, uShaft, ACPotential -> libRheoToolTutorialBCs.so
- linearExtrapolation, navierSlip -> libBCRheoTool.so

If schema/logs report RHEOTOOL_CUSTOM_BC_NOT_REGISTERED, the case uses a
boundary condition type that is not available in the installed libraries.
Diagnose it as an environment/source-template blocker. Do not invent alternate
library names, do not replace the boundary condition with codedFixedValue, and
do not reconstruct the time-dependent physical formula unless the source code or
the user explicitly supplies the formula.
