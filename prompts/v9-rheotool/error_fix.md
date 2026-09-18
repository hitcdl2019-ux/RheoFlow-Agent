Rewrite only requested files using Foundation OpenFOAM v9 rheoTool syntax. Do
not introduce v10 dictionary names and do not change CaseTarget.

For RheoTool custom boundary conditions, only use these installed-library names:
- uLid, uCos, HBprofile, uShaft, ACPotential -> libRheoToolTutorialBCs.so
- linearExtrapolation, navierSlip -> libBCRheoTool.so

Never add guessed libraries such as libRheoToolUtilities.so,
libRheoToolModels.so, or libRheoToolBoundaryConditions.so. If the error is
RHEOTOOL_CUSTOM_BC_NOT_REGISTERED, do not rewrite the physical boundary condition
or synthesize codedFixedValue; leave the case blocked and report that
the installed RheoTool runtime lacks the required boundary condition.
