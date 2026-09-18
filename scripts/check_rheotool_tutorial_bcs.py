#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_TUTORIAL_ROOT = Path('/opt/build/rheoTool/of90/tutorials')
DEFAULT_BC_LIBS = {
    'navierSlip': 'libBCRheoTool.so',
    'uLid': 'libRheoToolTutorialBCs.so',
    'uCos': 'libRheoToolTutorialBCs.so',
    'HBprofile': 'libRheoToolTutorialBCs.so',
    'uShaft': 'libRheoToolTutorialBCs.so',
    'ACPotential': 'libRheoToolTutorialBCs.so',
    'linearExtrapolation': 'libBCRheoTool.so',
}
DEFAULT_PPUTIL_LIBS = {
    'calcWi0': ('libpostProcessingRheoTool.so', 'libRheoToolTutorialPPUtils.so'),
    'calcCd': ('libpostProcessingRheoTool.so', 'libRheoToolTutorialPPUtils.so'),
    'calcKineticE': ('libpostProcessingRheoTool.so', 'libRheoToolTutorialPPUtils.so'),
    'calcVortexL': ('libpostProcessingRheoTool.so', 'libRheoToolTutorialPPUtils.so'),
    'calcW': ('libpostProcessingRheoTool.so', 'libRheoToolTutorialPPUtils.so'),
    'calcFfl': ('libpostProcessingRheoTool.so', 'libRheoToolTutorialPPUtils.so'),
}


def _default_lib_dirs() -> list[Path]:
    dirs: list[Path] = []
    for name in ('FOAM_USER_LIBBIN', 'FOAM_SITE_LIBBIN', 'FOAM_LIBBIN'):
        value = os.environ.get(name)
        if value:
            dirs.append(Path(value))
    for item in os.environ.get('LD_LIBRARY_PATH', '').split(os.pathsep):
        if item:
            dirs.append(Path(item))
    dirs.extend(
        Path(p)
        for p in (
            '/home/openfoam/platforms/linux64GccDPInt32Opt/lib',
            '/opt/openfoam9/platforms/linux64GccDPInt32Opt/lib',
        )
    )
    seen: set[Path] = set()
    result: list[Path] = []
    for path in dirs:
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


def _parse_bc_map(values: list[str]) -> dict[str, str]:
    mapping = dict(DEFAULT_BC_LIBS)
    for value in values:
        if '=' not in value:
            raise ValueError(f'Invalid --bc-lib entry, expected BC=library.so: {value}')
        bc_type, lib_name = value.split('=', 1)
        bc_type = bc_type.strip()
        lib_name = lib_name.strip()
        if not bc_type or not lib_name:
            raise ValueError(f'Invalid --bc-lib entry, expected BC=library.so: {value}')
        mapping[bc_type] = lib_name
    return mapping


def _parse_pputil_map(values: list[str]) -> dict[str, tuple[str, ...]]:
    mapping = dict(DEFAULT_PPUTIL_LIBS)
    for value in values:
        if '=' not in value:
            raise ValueError(f'Invalid --pputil-lib entry, expected ppUtil=library.so[,library2.so]: {value}')
        pputil_type, lib_names = value.split('=', 1)
        pputil_type = pputil_type.strip()
        libs = tuple(lib.strip() for lib in lib_names.split(',') if lib.strip())
        if not pputil_type or not libs:
            raise ValueError(f'Invalid --pputil-lib entry, expected ppUtil=library.so[,library2.so]: {value}')
        mapping[pputil_type] = libs
    return mapping


def _scan_tutorial_usage(tutorial_root: Path, bc_types: set[str]) -> dict[str, list[str]]:
    usage = {bc: [] for bc in sorted(bc_types)}
    if not tutorial_root.is_dir():
        return usage
    pattern = re.compile(r'\btype\s+(' + '|'.join(re.escape(bc) for bc in sorted(bc_types)) + r')\s*;')
    for path in sorted(tutorial_root.rglob('*')):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        for match in pattern.finditer(text):
            usage[match.group(1)].append(str(path.relative_to(tutorial_root)))
    return usage


def _scan_pputil_usage(tutorial_root: Path, pputil_types: set[str]) -> dict[str, list[str]]:
    usage = {pputil: [] for pputil in sorted(pputil_types)}
    if not tutorial_root.is_dir():
        return usage
    pattern = re.compile(r'\bfuncType\s+(' + '|'.join(re.escape(pputil) for pputil in sorted(pputil_types)) + r')\s*;')
    for path in sorted(tutorial_root.rglob('*')):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        for match in pattern.finditer(text):
            usage[match.group(1)].append(str(path.relative_to(tutorial_root)))
    return usage


def _library_candidates(lib_name: str, lib_dirs: list[Path]) -> list[Path]:
    return [path / lib_name for path in lib_dirs if (path / lib_name).is_file()]


def _library_registers_bc(paths: list[Path], bc_type: str) -> bool:
    token = bc_type.encode('utf-8')
    for path in paths:
        try:
            if token in path.read_bytes():
                return True
        except OSError:
            continue
    return False


def check_environment(
    tutorial_root: Path,
    lib_dirs: list[Path],
    bc_libs: dict[str, str],
    pputil_libs: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    usage = _scan_tutorial_usage(tutorial_root, set(bc_libs))
    checks: list[dict[str, Any]] = []
    ok = True
    for bc_type, lib_name in sorted(bc_libs.items()):
        candidates = _library_candidates(lib_name, lib_dirs)
        used_by = usage.get(bc_type, [])
        present = bool(candidates)
        registered = _library_registers_bc(candidates, bc_type) if present else False
        status = 'passed' if present and registered else 'failed'
        if status == 'failed':
            ok = False
        checks.append(
            {
                'bc_type': bc_type,
                'expected_library': lib_name,
                'status': status,
                'library_found': present,
                'registered': registered,
                'library_paths': [str(path) for path in candidates],
                'tutorial_usage_count': len(used_by),
                'tutorial_usage': used_by,
            }
        )
    pputil_checks: list[dict[str, Any]] = []
    if pputil_libs:
        pputil_usage = _scan_pputil_usage(tutorial_root, set(pputil_libs))
        for pputil_type, lib_names in sorted(pputil_libs.items()):
            used_by = pputil_usage.get(pputil_type, [])
            libraries: list[dict[str, Any]] = []
            status = 'passed'
            for lib_name in lib_names:
                candidates = _library_candidates(lib_name, lib_dirs)
                present = bool(candidates)
                registered = _library_registers_bc(candidates, pputil_type) if present else False
                if not present or (lib_name == lib_names[-1] and not registered):
                    status = 'failed'
                libraries.append(
                    {
                        'expected_library': lib_name,
                        'library_found': present,
                        'registered': registered,
                        'library_paths': [str(path) for path in candidates],
                    }
                )
            if status == 'failed':
                ok = False
            pputil_checks.append(
                {
                    'pputil_type': pputil_type,
                    'expected_libraries': list(lib_names),
                    'status': status,
                    'libraries': libraries,
                    'tutorial_usage_count': len(used_by),
                    'tutorial_usage': used_by,
                }
            )
    return {
        'ok': ok,
        'tutorial_root': str(tutorial_root),
        'library_search_dirs': [str(path) for path in lib_dirs],
        'checks': checks,
        'pputil_checks': pputil_checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Check RheoTool tutorial custom boundary-condition runtime support.')
    parser.add_argument('--tutorial-root', default=str(DEFAULT_TUTORIAL_ROOT))
    parser.add_argument('--lib-dir', action='append', default=[], help='Additional library search directory. May be repeated.')
    parser.add_argument('--bc-lib', action='append', default=[], help='Override/add expected mapping, e.g. uCos=libRheoToolTutorialBCs.so')
    parser.add_argument('--pputil-lib', action='append', default=[], help='Override/add expected mapping, e.g. calcVortexL=libpostProcessingRheoTool.so,libRheoToolTutorialPPUtils.so')
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON.')
    args = parser.parse_args(argv)

    bc_libs = _parse_bc_map(args.bc_lib)
    pputil_libs = _parse_pputil_map(args.pputil_lib)
    lib_dirs = [Path(value) for value in args.lib_dir] + _default_lib_dirs()
    report = check_environment(Path(args.tutorial_root), lib_dirs, bc_libs, pputil_libs)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"RheoTool tutorial BC environment check: {'passed' if report['ok'] else 'failed'}")
        print(f"tutorial_root: {report['tutorial_root']}")
        for item in report['checks']:
            usage = item['tutorial_usage_count']
            paths = ', '.join(item['library_paths']) or '<missing>'
            print(
                f"- {item['bc_type']} -> {item['expected_library']}: {item['status']} "
                f"(library_found={item['library_found']}, registered={item['registered']}, tutorial_usage={usage})"
            )
            print(f"  library_paths: {paths}")
            for rel in item['tutorial_usage'][:5]:
                print(f"  used_by: {rel}")
            if len(item['tutorial_usage']) > 5:
                print(f"  used_by: ... +{len(item['tutorial_usage']) - 5} more")
        for item in report['pputil_checks']:
            print(
                f"- {item['pputil_type']} -> {', '.join(item['expected_libraries'])}: "
                f"{item['status']} (tutorial_usage={item['tutorial_usage_count']})"
            )
            for lib in item['libraries']:
                paths = ', '.join(lib['library_paths']) or '<missing>'
                print(
                    f"  library {lib['expected_library']}: "
                    f"found={lib['library_found']}, registered={lib['registered']}, paths={paths}"
                )
            for rel in item['tutorial_usage'][:5]:
                print(f"  used_by: {rel}")
            if len(item['tutorial_usage']) > 5:
                print(f"  used_by: ... +{len(item['tutorial_usage']) - 5} more")
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
