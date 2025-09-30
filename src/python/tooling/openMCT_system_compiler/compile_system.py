"""
Generate an OpenMCT-style JSON (`system_composition.json`) from a composed
system dictionary produced by `compose_result_to_dict`.

Behavior:
- Resolves dsdl_python_bindings base from --dsdl-base CLI argument or PYTHONPATH (in that order).
- Loads composed system only from get_compose_result_from_env().
- Saves output to path specified by OPENMCT_SYSTEM_COMP_PATH env var (dir or file).
  If not set, writes to ./system_composition.json
- Provides a simple CLI entry point.
"""
import argparse
import json
import logging
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# --- DSDL bindings resolution (cached) ---
_DSDL_BASE: Optional[Path] = None


def _set_dsdl_base(path: str) -> Path:
    """Validate and set the module-level DSDL base path."""
    global _DSDL_BASE
    p = Path(path).resolve()
    if not p.exists():
        raise SystemExit(f"Specified DSDL base path does not exist: {p}")
    _DSDL_BASE = p
    log.debug("DSDL base resolved and cached: %s", _DSDL_BASE)
    return _DSDL_BASE


def resolve_dsdl_bindings_base(cli_base: Optional[str] = None) -> Path:
    """
    Resolve the dsdl_python_bindings base directory.

    Resolution precedence:
      1. cli_base (if provided) - validated and cached
      2. First entry in PYTHONPATH (if set and exists) - cached

    Raises SystemExit if no candidate can be resolved.

    Once resolved the path is cached and subsequent calls return the cached value.
    """
    global _DSDL_BASE
    if _DSDL_BASE is not None:
        return _DSDL_BASE

    # 1) CLI-provided override
    if cli_base:
        return _set_dsdl_base(cli_base)

    # 2) Check PYTHONPATH environment variable (first entry)
    pythonpath = os.environ.get("PYTHONPATH", "")
    if pythonpath:
        first_entry = pythonpath.split(os.pathsep)[0]
        if first_entry:
            p = Path(first_entry).resolve()
            if p.exists():
                log.debug("Using PYTHONPATH entry as dsdl base: %s", p)
                _DSDL_BASE = p
                return _DSDL_BASE
            else:
                raise SystemExit(f"PYTHONPATH entry does not exist: {p}")

    # If neither is available, exit with an error
    raise SystemExit(
        "DSDL bindings path not specified. Please either:\n"
        "  1) Use --dsdl-base CLI argument with absolute path, or\n"
        "  2) Set PYTHONPATH environment variable to include the bindings path"
    )


# Note: DSDL bindings are resolved and imported inside `tooling.dsdl_reader`.
try:
    from nova_can.utils.compose_system import get_compose_result_from_env, compose_result_to_dict  # noqa: E402
    from tooling.dsdl_reader.dsdl_reader import get_transformed_dsdl  # noqa: E402
except Exception as e:
    log.debug("Imports of project modules failed; continuing — may fail later when used. Error: %s", e)


# --- load composed system only from env-provided composition ---
def load_composed_system_dict() -> dict:
    """
    Retrieve the composed system *only* via get_compose_result_from_env().
    If that returns None or raises, exit with a helpful error.
    """
    try:
        result = get_compose_result_from_env()
    except Exception as e:
        log.debug("get_compose_result_from_env raised an exception.", exc_info=True)
        raise SystemExit("Failed to retrieve composed system from environment via get_compose_result_from_env().") from e

    if result is None:
        raise SystemExit(
            "No composed system available from environment. "
            "This tool expects compose data to be provided via get_compose_result_from_env()."
        )

    # convert/normalize using existing helper
    try:
        return compose_result_to_dict(result)
    except Exception as e:
        log.debug("compose_result_to_dict failed.", exc_info=True)
        raise SystemExit("Failed to convert compose result to dict via compose_result_to_dict().") from e


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
    The resolved base is cached after the first resolution so subsequent calls reuse it.
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
        if isinstance(v, (list, tuple)):
            return [to_json_primitive(x) for x in v]
        if isinstance(v, dict):
            return {str(k): to_json_primitive(val) for k, val in v.items()}
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
                        # All-bool composite message: add as a single item with all bool fields and one timestamp
                        values: List[Dict[str, Any]] = []
                        
                        for fe in field_entries:
                            field_key = fe.get('name') or ''
                            field_fmt = fe.get('format') or ''
                            field_const = bool(fe.get('constant', False))
                            
                            value_entry: Dict[str, Any] = {
                                "key": field_key,
                                "name": field_display_name(field_key),
                                "format": field_fmt,
                                "constant": field_const,
                            }
                            
                            if field_const and ("value" in fe):
                                value_entry["value"] = fe.get("value")
                            
                            values.append(value_entry)
                        
                        # Add single timestamp for the entire message
                        try:
                            ts_entry = make_timestamp_entry()
                            if not any(v.get('key') == ts_entry.get('key') for v in values):
                                values.append(ts_entry)
                        except Exception:
                            log.debug('Failed to append timestamp entry to all-bool transmit %s', tname, exc_info=True)
                        
                        item = {
                            "name": normalize_name(tname),
                            "key": f"{dev_key}.transmit.{make_key(tname)}",
                            "values": values,
                        }
                        transmit_items.append(item)
                        
                    else:
                        # Other composite messages: create a folder with individual items for each field
                        composite_folder_key = f"{dev_key}.transmit.{make_key(tname)}"
                        composite_folder_items = []
                        
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

                            # Each field gets its own timestamp
                            try:
                                ts_entry = make_timestamp_entry()
                                if not any(v.get('key') == ts_entry.get('key') for v in values):
                                    values.append(ts_entry)
                            except Exception:
                                log.debug('Failed to append timestamp entry to composite field %s.%s', tname, field_key, exc_info=True)

                            item = {
                                "name": field_display_name(field_key),
                                "key": f"{composite_folder_key}.{make_key(field_key)}",
                                "values": values,
                            }
                            composite_folder_items.append(item)
                        
                        # Add the folder for this composite message
                        composite_folder = {
                            "name": normalize_name(tname),
                            "key": composite_folder_key,
                            "folders": [],
                            "items": composite_folder_items
                        }
                        transmit_folders.append(composite_folder)

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
    p.add_argument("--dsdl-base", type=str, default=None,
                   help="Optional explicit DSDL bindings base path. If set, this overrides PYTHONPATH discovery.")
    p.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging (DEBUG).")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.verbose:
        log.setLevel(logging.DEBUG)
        log.debug("Verbose logging enabled")

    # Resolve and cache DSDL base once (CLI override preferred)
    try:
        resolve_dsdl_bindings_base(getattr(args, "dsdl_base", None))
    except SystemExit as e:
        log.error("Failed to resolve DSDL bindings base: %s", e)
        return 1

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
# End of file