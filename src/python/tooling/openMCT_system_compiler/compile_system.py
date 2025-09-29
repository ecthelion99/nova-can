"""
Generate an OpenMCT-style JSON (`system_composition.json`) from a composed
system dictionary produced by `compose_result_to_dict`.

Behavior:
 - Resolves dsdl_python_bindings base from PYTHONPATH / sys.path / repo / fallback.
 - Produces transmit messages as 'values' arrays (each value: key, name, format, constant[, value]).
 - Saves output to path specified by OPENMCT_SYSTEM_COMP_PATH env var (dir or file).
   If not set, writes to ./system_composition.json
 - Provides a simple CLI entry point.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import numbers
import fractions
import decimal
import numpy as np

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# --- Optional: prefer repo src imports when running from repo (keeps behaviour stable) ---
repo_src = Path(__file__).resolve().parents[1] / 'src' / 'python'
if str(repo_src) not in sys.path:
    sys.path.insert(0, str(repo_src))


# --- DSDL bindings resolution (PYTHONPATH-first, then sys.path, repo-local, fallback) ---
def resolve_dsdl_bindings_base(explicit_base: Optional[str] = None,
                               fallback: str = "/home/pih/FYP/nova-can/dsdl_python_bindings") -> Path:
    """Resolve the dsdl_python_bindings base directory.

    Priority:
      1) explicit_base (if provided and exists)
      2) first existing PYTHONPATH entry (prefer one that looks like bindings)
      3) sys.path entries that look like bindings base
      4) repo-local <repo_root>/dsdl_python_bindings
      5) fallback
    """
    if explicit_base:
        p = Path(explicit_base)
        if p.exists():
            log.debug("Using explicit dsdl base: %s", p)
            return p
        log.debug("Explicit dsdl base provided but does not exist: %s", p)

    def looks_like_bindings_base(p: Path) -> bool:
        if not p.exists():
            return False
        # folder named dsdl_python_bindings (explicit)
        if (p / "dsdl_python_bindings").exists():
            return True
        # contains a package dir or __init__.py children OR package-like names
        try:
            for child in p.iterdir():
                if child.is_dir() and (child / "__init__.py").exists():
                    return True
                if child.is_dir() and (child.name.endswith("dsdl") or child.name.startswith("nova_dsdl")):
                    return True
        except Exception:
            pass
        return False

    # 2) PYTHONPATH
    py = os.environ.get("PYTHONPATH", "")
    if py:
        for entry in py.split(os.pathsep):
            if not entry:
                continue
            p = Path(entry)
            if p.exists():
                if looks_like_bindings_base(p):
                    log.debug("Found dsdl base from PYTHONPATH (looks like bindings): %s", p)
                    return p
                log.debug("Using first existing PYTHONPATH entry as dsdl base: %s", p)
                return p

    # 3) sys.path
    for entry in sys.path:
        if not entry:
            continue
        p = Path(entry)
        if looks_like_bindings_base(p):
            log.debug("Found dsdl base from sys.path: %s", p)
            return p

    # 4) repo-local
    repo_local = Path(__file__).resolve().parents[1] / 'dsdl_python_bindings'
    if repo_local.exists():
        log.debug("Using repo-local dsdl bindings dir: %s", repo_local)
        return repo_local

    # 5) fallback
    log.debug("Falling back to hard-coded dsdl base: %s", fallback)
    return Path(fallback)


# Note: DSDL bindings are resolved and imported inside `tooling.dsdl_reader`.
# The compiler no longer inserts binding paths into sys.path at import time to
# avoid interfering with other import resolution and to centralize binding
# discovery in the dsdl reader.


# Now import project-specific code that may depend on the above sys.path change
try:
    from nova_can.utils.compose_system import get_compose_result_from_env, compose_result_to_dict  # noqa: E402
    from tooling.dsdl_reader.dsdl_reader import get_transformed_dsdl  # noqa: E402
except Exception as e:
    log.debug("Imports of project modules failed; continuing — may fail later when used. Error: %s", e)


# --- load composed system JSON or env-provided composition ---
def load_composed_system_dict() -> dict:
    """
    Try to get live compose result from env via get_compose_result_from_env().
    Otherwise, search for composed_system.json or system_composition.json in cwd and repo root.
    """
    try:
        result = get_compose_result_from_env()
        if result is not None:
            return compose_result_to_dict(result)
    except Exception:
        log.debug("get_compose_result_from_env not available or failed; falling back to files")

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


# --- small helpers ---
def make_timestamp_entry() -> dict:
    return {
        "key": "utc",
        "source": "timestamp",
        "name": "Timestamp",
        "units": "utc",
        "format": "integer",
        "hints": {"domain": 1},
    }


def port_type_to_file_path(port_type: str, base_path: Optional[str] = None) -> str:
    """
    Convert a port_type like 'nova_dsdl.sensors.msg.Velocity.1.0' into a filesystem path
    to the generated binding file. If base_path is None this uses resolve_dsdl_bindings_base().
    """
    if not port_type:
        raise ValueError("port_type must be provided")

    parts = port_type.split('.')
    if len(parts) < 3:
        raise ValueError(f"port_type has too few components: {port_type!r}")

    name = parts[-3]
    major = parts[-2]
    minor = parts[-1]
    filename = f"{name}_{major}_{minor}.py"
    path_parts = parts[:-3]

    resolved_base = Path(base_path) if base_path else resolve_dsdl_bindings_base()
    file_path = resolved_base.joinpath(*path_parts, filename)
    return str(file_path)


def get_dsdl_format(port_type: str) -> List[Dict[str, Any]]:
    """
    Parse a DSDL binding file (via get_transformed_dsdl) and return a list of
    entries like: { "name": <field_name>, "format": <type_token>, "constant": bool, "value": ... }
    """
    def to_json_primitive(v):
        if v is None or isinstance(v, (str, bool, int, float)):
            return v
        if isinstance(v, fractions.Fraction):
            return int(v) if v.denominator == 1 else float(v)
        if isinstance(v, decimal.Decimal):
            try:
                return int(v)
            except Exception:
                return float(v)
        if isinstance(v, np.generic):
            try:
                return v.item()
            except Exception:
                return float(v)
        if isinstance(v, (np.ndarray,)):
            try:
                return v.tolist()
            except Exception:
                return str(v)
        if isinstance(v, numbers.Number):
            return v
        if isinstance(v, (list, tuple)):
            return [to_json_primitive(x) for x in v]
        if isinstance(v, dict):
            return {k: to_json_primitive(val) for k, val in v.items()}
        return str(v)

    def normalize_format(fmt: object) -> str:
        if isinstance(fmt, str):
            parts = fmt.split()
            return parts[-1] if parts else fmt
        return str(fmt)

    try:
        dsdl_path = port_type_to_file_path(port_type)
        if not Path(dsdl_path).exists():
            raise FileNotFoundError(f"DSDL binding file not found: {dsdl_path}")
        #print("dsdl_path =", dsdl_path)
        dsdl_data = get_transformed_dsdl(dsdl_path)
        format_list: List[Dict[str, Any]] = []

        for item in dsdl_data.get("data", []):
            fmt = normalize_format(item.get("format"))
            format_entry = {
                "name": item.get("name"),
                "format": fmt,
            }
            if item.get("value") is not None:
                format_entry.update({
                    "constant": True,
                    "value": to_json_primitive(item.get("value")),
                })
            else:
                format_entry["constant"] = False

            format_list.append(format_entry)

        return format_list
    except Exception as e:
        log.warning("Failed to process DSDL type %s: %s", port_type, e)
        return []


def field_display_name(field_key: str) -> str:
    """
    Convert a field key like "error_flags.stall" to "Error Flags/Stall"
    - '.' -> '/'
    - '_' -> ' ' (then Title case each word)
    """
    if not field_key:
        return ''
    parts = field_key.split('.')
    display_parts = []
    for part in parts:
        words = [w.capitalize() for w in part.split('_') if w != ""]
        display_parts.append(' '.join(words))
    return '/'.join(display_parts)


def is_atomic_message(field_entries: List[Dict[str, Any]]) -> bool:
    """
    Check if a message is atomic (only one non-constant field).
    Constants don't count towards the field count.
    """
    non_constant_fields = [f for f in field_entries if not f.get('constant', False)]
    return len(non_constant_fields) == 1


def is_all_bool_message(field_entries: List[Dict[str, Any]]) -> bool:
    """
    Check if all fields (including constants) in a message are of type "bool".
    """
    return all(f.get('format') == 'bool' for f in field_entries)


# --- Build OpenMCT dictionary structure ---
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

    def normalize_name(s: str) -> str:
        if s is None:
            return ''
        s = str(s).strip()
        if ('_' not in s and ' ' not in s) and (is_upper_camel_case(s) or is_all_upper(s)):
            return s

        parts = [p for p in re.split(r'[_\s]+', s) if p]
        normalized_parts = []
        for p in parts:
            if is_upper_camel_case(p) or is_all_upper(p):
                normalized_parts.append(p)
            else:
                normalized_parts.append(p.capitalize())
        return ' '.join(normalized_parts)

    def is_upper_camel_case(s: str) -> bool:
        if not s:
            return False
        return ('_' not in s and ' ' not in s and s[0].isupper() and
                any(ch.isupper() for ch in s[1:]))

    def is_all_upper(s: str) -> bool:
        return s.isupper()

    devices = system.get('devices', {})
    interfaces = compose_dict.get('interfaces', {})

    system_map = {}
    for dev_name, dev in devices.items():
        src = dev.get('source_system') or 'unknown_system'
        system_map.setdefault(src, []).append(dev)

    for src_system, devs_in_system in sorted(system_map.items()):
        src_key = f"{system_key}.{make_key(src_system)}"
        src_folder = {"name": normalize_name(src_system), "key": src_key, "folders": []}

        device_type_map = {}
        for dev in devs_in_system:
            dtype = dev.get('device_type', 'unknown')
            device_type_map.setdefault(dtype, []).append(dev)

        for dtype, dev_list in sorted(device_type_map.items()):
            dtype_key = f"{src_key}.{make_key(dtype)}"
            dtype_folder = {"name": normalize_name(dtype), "key": dtype_key, "folders": []}

            for dev in sorted(dev_list, key=lambda d: (d.get('name') or '').lower()):
                dev_name = dev.get('name')
                dev_key = f"{dtype_key}.{make_key(dev_name)}"

                int_name = dev.get('interface_name')
                int_def = interfaces.get(int_name, {}) if int_name else {}

                # Receive items: unchanged
                receive_items = []
                for rname, rport in (int_def.get('messages', {}).get('receive') or {}).items():
                    port_type = rport.get('port_type')

                    item = {
                        "name": normalize_name(rname),
                        "key": f"{dev_key}.receive.{make_key(rname)}",
                        "format": get_dsdl_format(port_type) if port_type else []
                    }
                    receive_items.append(item)

                # Transmit items: handle atomic, all-bool composite, and other composite messages differently
                transmit_items = []
                transmit_folders = []
                
                for tname, tport in (int_def.get('messages', {}).get('transmit') or {}).items():
                    port_type = tport.get('port_type')

                    # Get fields from the DSDL binding
                    field_entries = get_dsdl_format(port_type) if port_type else []

                    # If no fields were discovered, keep a single item for the message with only a timestamp
                    if not field_entries:
                        try:
                            item = {
                                "name": normalize_name(tname),
                                "key": f"{dev_key}.transmit.{make_key(tname)}",
                                "values": [make_timestamp_entry()],
                            }
                            transmit_items.append(item)
                        except Exception:
                            log.debug('Failed to create empty-transmit item for %s', tname, exc_info=True)
                        continue

                    # Check if message is atomic or composite
                    if is_atomic_message(field_entries):
                        # Atomic message: add as a single item to transmit items
                        # Find the non-constant field
                        non_constant_field = next((f for f in field_entries if not f.get('constant', False)), field_entries[0])
                        field_key = non_constant_field.get('name') or ''
                        field_fmt = non_constant_field.get('format') or ''
                        
                        value_entry: Dict[str, Any] = {
                            "key": field_key,
                            "name": field_display_name(field_key),
                            "format": field_fmt,
                            "constant": False,
                            "hints": {"range": 1},
                        }
                        
                        values: List[Dict[str, Any]] = [value_entry]
                        
                        # Add timestamp
                        try:
                            ts_entry = make_timestamp_entry()
                            if not any(v.get('key') == ts_entry.get('key') for v in values):
                                values.append(ts_entry)
                        except Exception:
                            log.debug('Failed to append timestamp entry to atomic transmit %s', tname, exc_info=True)
                        
                        item = {
                            "name": normalize_name(tname),
                            "key": f"{dev_key}.transmit.{make_key(tname)}",
                            "values": values,
                        }
                        transmit_items.append(item)
                        
                    elif is_all_bool_message(field_entries):
                        # All-bool composite message: create a folder with individual items
                        bool_folder_key = f"{dev_key}.transmit.{make_key(tname)}"
                        bool_folder_items = []
                        
                        for fe in field_entries:
                            field_key = fe.get('name') or ''
                            field_fmt = fe.get('format') or ''
                            field_const = bool(fe.get('constant', False))
                            
                            value_entry: Dict[str, Any] = {
                                "key": field_key,
                                "name": field_display_name(field_key),
                                "format": field_fmt,
                                "constant": field_const,
                                "hints": {"range": 1},
                            }
                            
                            if field_const and ("value" in fe):
                                value_entry["value"] = fe.get("value")
                            
                            values: List[Dict[str, Any]] = [value_entry]
                            
                            # Each bool field gets its own timestamp
                            try:
                                ts_entry = make_timestamp_entry()
                                if not any(v.get('key') == ts_entry.get('key') for v in values):
                                    values.append(ts_entry)
                            except Exception:
                                log.debug('Failed to append timestamp entry to bool field %s.%s', tname, field_key, exc_info=True)
                            
                            item = {
                                "name": field_display_name(field_key),
                                "key": f"{bool_folder_key}.{make_key(field_key)}",
                                "values": values,
                            }
                            bool_folder_items.append(item)
                        
                        # Add the folder for this all-bool message
                        bool_folder = {
                            "name": normalize_name(tname),
                            "key": bool_folder_key,
                            "folders": [],
                            "items": bool_folder_items
                        }
                        transmit_folders.append(bool_folder)
                        
                    else:
                        # Other composite messages: split into individual items in transmit items
                        for fe in field_entries:
                            field_key = fe.get('name') or ''
                            field_fmt = fe.get('format') or ''
                            field_const = bool(fe.get('constant', False))

                            value_entry: Dict[str, Any] = {
                                "key": field_key,
                                "name": field_display_name(field_key),
                                "format": field_fmt,
                                "constant": field_const,
                                "hints": {"range": 1},
                            }
                            
                            if field_const and ("value" in fe):
                                value_entry["value"] = fe.get("value")

                            values: List[Dict[str, Any]] = [value_entry]

                            # Ensure every transmit item includes a UTC timestamp entry
                            try:
                                ts_entry = make_timestamp_entry()
                                if not any(v.get('key') == ts_entry.get('key') for v in values):
                                    values.append(ts_entry)
                            except Exception:
                                log.debug('Failed to append timestamp entry to transmit field %s.%s', tname, field_key, exc_info=True)

                            # Item name: <Message>.<field_key> (preserve readable message name + raw field key)
                            item = {
                                "name": f"{normalize_name(tname)}.{field_key}",
                                "key": f"{dev_key}.transmit.{make_key(tname)}.{make_key(field_key)}",
                                "values": values,
                            }
                            transmit_items.append(item)

                # Create transmit folder structure
                transmit_folder = {
                    "name": "Transmit",
                    "key": f"{dev_key}.transmit",
                    "folders": transmit_folders,
                    "items": transmit_items
                }

                dev_folder = {
                    "name": normalize_name(dev_name),
                    "key": dev_key,
                    "folders": [
                        {"name": "Receive", "key": f"{dev_key}.receive", "folders": [], "items": receive_items},
                        transmit_folder,
                    ],
                }

                dtype_folder['folders'].append(dev_folder)

            src_folder['folders'].append(dtype_folder)

        openMCT_dictionary['folders'].append(src_folder)

    return openMCT_dictionary


# --- Output path resolution and saving logic ---
def resolve_output_path(env_var: str = "OPENMCT_SYSTEM_COMP_PATH",
                        default_filename: str = "system_composition.json") -> Path:
    """
    Determine where to save the generated JSON.
    - If env_var not set: return cwd/default_filename
    - If env_var set and is a directory: return that_dir/default_filename
    - If env_var set and looks like a file (has a suffix) use that exact path (create parents)
    - If env_var set and doesn't exist: attempt to create directory if no suffix, otherwise treat as file path
    """
    val = os.environ.get(env_var)
    if not val:
        return Path.cwd() / default_filename

    p = Path(val)

    # If it's a directory (exists or ends with os.sep), use directory + default_filename
    if p.exists() and p.is_dir():
        return p / default_filename

    # Heuristic: if provided path has a suffix like .json, treat as file
    if p.suffix:
        parent = p.parent
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
        return p

    # If path doesn't exist and has no suffix: create directory and use default_filename inside it
    try:
        p.mkdir(parents=True, exist_ok=True)
        return p / default_filename
    except Exception:
        # Fallback to cwd
        log.warning("Could not create directory for OPENMCT_SYSTEM_COMP_PATH='%s', falling back to cwd", val)
        return Path.cwd() / default_filename


def save_openmct_json(openmct: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open('w', encoding='utf-8') as f:
        json.dump(openmct, f, indent=4, ensure_ascii=False)
    log.info("Wrote OpenMCT composition to %s", out_path.resolve())


# --- CLI entrypoint ---
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate OpenMCT-style system composition JSON.")
    p.add_argument("--out", "-o", type=str, default=None,
                   help="Optional explicit output file or directory. Overrides OPENMCT_SYSTEM_COMP_PATH.")
    p.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging (DEBUG).")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.verbose:
        log.setLevel(logging.DEBUG)
        log.debug("Verbose logging enabled")

    try:
        compose_dict = load_composed_system_dict()
    except SystemExit as e:
        log.error("Failed to load composed system: %s", e)
        return 2
    except Exception as e:
        log.exception("Unexpected error while loading composed system: %s", e)
        return 3

    openmct = build_openmct_dict(compose_dict)

    # Determine output path: CLI override > env var > cwd
    if args.out:
        out_candidate = Path(args.out)
        if out_candidate.exists() and out_candidate.is_dir():
            out_path = out_candidate / "system_composition.json"
        elif out_candidate.suffix:
            # treat as file path
            out_candidate.parent.mkdir(parents=True, exist_ok=True)
            out_path = out_candidate
        else:
            # treat as directory to be created
            out_candidate.mkdir(parents=True, exist_ok=True)
            out_path = out_candidate / "system_composition.json"
    else:
        out_path = resolve_output_path()

    try:
        save_openmct_json(openmct, out_path)
    except Exception as e:
        log.exception("Failed to write OpenMCT JSON: %s", e)
        return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(main())