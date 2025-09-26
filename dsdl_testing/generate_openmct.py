#!/usr/bin/env python3
"""
Generate an OpenMCT-style JSON (`system_composition.json`) from a composed
system dictionary produced by `compose_result_to_dict`.
"""
import json
import sys
import re
from pathlib import Path

# ensure project src is on PYTHONPATH when running outside package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'python'))

from nova_can.utils.compose_system import get_compose_result_from_env, compose_result_to_dict


def load_composed_system_dict() -> dict:
    result = get_compose_result_from_env()
    if result is not None:
        return compose_result_to_dict(result)

    cwd = Path.cwd()
    repo_root = Path(__file__).resolve().parents[1]

    candidates = [
        cwd / 'composed_system.json',
        cwd / 'system_composition.json',
        repo_root / 'composed_system.json',
        repo_root / 'system_composition.json',
    ]

    for path in candidates:
        if path.exists():
            with path.open('r', encoding='utf-8') as f:
                return json.load(f)

    raise SystemExit("No composed system available: set env vars or create composed_system.json")


def make_timestamp_entry() -> dict:
    return {
        "key": "utc",
        "source": "timestamp",
        "name": "Timestamp",
        "units": "utc",
        "format": "integer",
        "hints": {"domain": 1},
    }


def build_openmct_dict(compose_dict: dict) -> dict:
    system = compose_dict.get('system') or {}
    system_name = 'Rover'
    system_key = 'rover'

    openMCT_dictionary = {
        "name": system_name,
        "key": system_key,
        "folders": [],
    }

    def make_key(s: str) -> str:
        if s is None:
            return ''
        return str(s).lower()

    def is_upper_camel_case(s: str) -> bool:
        """Detect UpperCamelCase / PascalCase (e.g. CurrentCommand)."""
        if not s:
            return False
        # must not contain underscores or spaces; first char uppercase; at least one other uppercase later
        return ('_' not in s and ' ' not in s and s[0].isupper() and
                any(ch.isupper() for ch in s[1:]))

    def is_all_upper(s: str) -> bool:
        """Detect all-uppercase tokens (acronyms) like GPS."""
        return s.isupper()

    def normalize_name(s: str) -> str:
        """Normalize names:
           - If UpperCamelCase (no underscores) => preserve as-is (CurrentCommand).
           - If all-upper token (GPS) => preserve as-is.
           - Otherwise replace underscores with spaces and Title Case each word.
        """
        if s is None:
            return ''
        s = str(s).strip()
        # If there are no underscores/spaces and it's UpperCamelCase or ALL CAPS, keep it
        if ('_' not in s and ' ' not in s) and (is_upper_camel_case(s) or is_all_upper(s)):
            return s

        # Replace underscores (and multiple underscores/spaces) with single space, split into parts
        parts = [p for p in re.split(r'[_\s]+', s) if p]
        normalized_parts = []
        for p in parts:
            # Preserve part if it looks like PascalCase or an acronym
            if is_upper_camel_case(p) or is_all_upper(p):
                normalized_parts.append(p)
            else:
                # Otherwise title-case the part (first letter uppercase, rest lowercase)
                normalized_parts.append(p.capitalize())
        return ' '.join(normalized_parts)

    # group devices by source_system then device_type
    devices = system.get('devices', {})
    interfaces = compose_dict.get('interfaces', {})

    system_map = {}
    for dev_name, dev in devices.items():
        src = dev.get('source_system') or 'unknown_system'
        system_map.setdefault(src, []).append(dev)

    # For each source system, create a folder containing device-type folders
    for src_system, devs_in_system in sorted(system_map.items()):
        src_key = f"{system_key}.{make_key(src_system)}"
        src_folder = {"name": normalize_name(src_system), "key": src_key, "folders": []}

        # group these devices by device_type
        device_type_map = {}
        for dev in devs_in_system:
            dtype = dev.get('device_type', 'unknown')
            device_type_map.setdefault(dtype, []).append(dev)

        for dtype, dev_list in sorted(device_type_map.items()):
            dtype_key = f"{src_key}.{make_key(dtype)}"
            dtype_folder = {"name": normalize_name(dtype), "key": dtype_key, "folders": []}

            for dev in sorted(dev_list, key=lambda d: d.get('name')):
                dev_name = dev.get('name')
                dev_key = f"{dtype_key}.{make_key(dev_name)}"

                int_name = dev.get('interface_name')
                int_def = interfaces.get(int_name, {}) if int_name else {}

                receive_items = []
                for rname, rport in (int_def.get('messages', {}).get('receive') or {}).items():
                    item = {
                        "name": normalize_name(rname),
                        "key": f"{dev_key}.receive.{make_key(rname)}",
                        "format": []
                    }
                    receive_items.append(item)

                transmit_items = []
                for tname, tport in (int_def.get('messages', {}).get('transmit') or {}).items():
                    values = []
                    values.append(make_timestamp_entry())

                    item = {
                        "name": normalize_name(tname),
                        "key": f"{dev_key}.transmit.{make_key(tname)}",
                        "values": values,
                    }
                    transmit_items.append(item)

                dev_folder = {
                    "name": normalize_name(dev_name),
                    "key": dev_key,
                    "folders": [
                        {"name": "Receive", "key": f"{dev_key}.receive", "folders": [], "items": receive_items},
                        {"name": "Transmit", "key": f"{dev_key}.transmit", "folders": [], "items": transmit_items},
                    ],
                }

                dtype_folder['folders'].append(dev_folder)

            src_folder['folders'].append(dtype_folder)

        openMCT_dictionary['folders'].append(src_folder)

    return openMCT_dictionary


def main():
    compose_dict = load_composed_system_dict()
    openmct = build_openmct_dict(compose_dict)

    out_path = Path('system_composition.json')
    with out_path.open('w', encoding='utf-8') as f:
        json.dump(openmct, f, indent=4, ensure_ascii=False)

    print(f"Wrote OpenMCT composition to {out_path.resolve()}")


if __name__ == '__main__':
    main()
