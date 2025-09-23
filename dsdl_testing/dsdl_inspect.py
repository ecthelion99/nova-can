#!/usr/bin/env python3
"""
dsdl_inspect.py

Usage:
    python dsdl_inspect.py /path/to/Type.1.0.dsdl /path/to/root_namespace_dir

Requires: pydsdl (install in your venv)
This script:
 - parses the given .dsdl file using pydsdl.read_files()
 - returns a dictionary describing the type:
    - for a message: fields + constants
    - for a service: request dict and response dict (each with fields + constants)
 - prints the dictionary in a readable format
"""

from pathlib import Path
import sys
import pydsdl
from typing import Any, Dict, List
import pprint
# ----------------------
# Helpers to convert pydsdl objects to plain data
# ----------------------

def safe_int(x):
    """Try to coerce pydsdl rational-like values to int when possible."""
    try:
        return int(x)
    except Exception:
        return str(x)

def format_data_type(dt: Any) -> str:
    """
    Return a compact human-readable string for a pydsdl data type object.
    Handles common primitive types (unsigned/signed integers, boolean, float),
    structures and falls back to the class name.
    """
    cname = dt.__class__.__name__.lower()
    # signed/unsigned integer types
    if "unsignedinteger" in cname or "unsigned" in cname and hasattr(dt, "bit_length"):
        try:
            return f"uint{dt.bit_length}"
        except Exception:
            return "uint"
    if "signedinteger" in cname or "signed" in cname and hasattr(dt, "bit_length"):
        try:
            return f"int{dt.bit_length}"
        except Exception:
            return "int"
    if "boolean" in cname or "bool" in cname:
        return "bool"
    if "float" in cname and hasattr(dt, "bit_length"):
        try:
            return f"float{dt.bit_length}"
        except Exception:
            return "float"
    # structure types often have a name attribute (fully-qualified)
    if hasattr(dt, "name") and dt.name:
        return dt.name
    # arrays / dynamic types might have element_type / element_count attributes
    if hasattr(dt, "element_type"):
        return f"array[{format_data_type(dt.element_type)}]"
    # fallback: show the class name
    return dt.__class__.__name__

def extract_constants(constants_list) -> List[Dict[str, Any]]:
    """Given pydsdl constants sequence, return list of dicts {name,type,value}."""
    out = []
    for c in constants_list:
        # c has attributes: name, data_type, value
        try:
            ctype = format_data_type(c.data_type)
        except Exception:
            ctype = str(type(c.data_type))
        try:
            cval = safe_int(c.value)
        except Exception:
            cval = str(c.value)
        out.append({"name": c.name, "type": ctype, "value": cval})
    return out

def extract_fields(fields_list) -> List[Dict[str, Any]]:
    """Given pydsdl Field sequence, return list of dicts {name,type}."""
    out = []
    for f in fields_list:
        # f has attributes: name, data_type
        try:
            ftype = format_data_type(f.data_type)
        except Exception:
            ftype = str(type(f.data_type))
        out.append({"name": f.name, "type": ftype})
    return out

# ----------------------
# Main parsing function
# ----------------------

def parse_dsdl_file(dsdl_file: Path, root_namespace: Path) -> Dict[str, Any]:
    """
    Parse a single .dsdl file and return a dictionary describing it.

    Output schema (examples):

    For a message:
    {
      "kind": "message",
      "name": "<fully.qualified.name>",
      "sealed": True/False,
      "fields": [ {"name":"value", "type":"int16"}, ... ],
      "constants": [ {"name":"X","type":"uint2","value":0}, ... ]
    }

    For a service:
    {
      "kind": "service",
      "name": "<fully.qualified.service.name>",
      "request": { "sealed":..., "fields":[...], "constants":[...] },
      "response": { "sealed":..., "fields":[...], "constants":[...] }
    }
    """
    if not dsdl_file.exists():
        raise FileNotFoundError(f"DSDL file not found: {dsdl_file}")
    if not root_namespace.exists():
        raise FileNotFoundError(f"Root namespace dir not found: {root_namespace}")

    parsed, dependent = pydsdl.read_files(
        dsdl_files=[str(dsdl_file)],
        root_namespace_directories_or_names=[str(root_namespace)],
        lookup_directories=None,
        print_output_handler=None,
        allow_unregulated_fixed_port_id=False,
    )

    if not parsed:
        raise RuntimeError("pydsdl returned no parsed types")

    # We expect exactly one top-level type from the file (common case).
    top = parsed[0]
    cls_name = top.__class__.__name__.lower()

    if "service" in cls_name:  # ServiceType
        # service_type.fields -> typically two fields: request and response
        # Each field has .data_type which is a StructureType
        service_dict = {"kind": "service", "name": getattr(top, "name", str(top))}
        # extract request and response
        # pydsdl keeps them in top.fields (first -> request, second -> response)
        if not getattr(top, "fields", None) or len(top.fields) < 2:
            raise RuntimeError("Service type did not contain request+response fields")

        req_field = top.fields[0]
        res_field = top.fields[1]
        req_struct = req_field.data_type
        res_struct = res_field.data_type

        service_dict["request"] = {
            "name": getattr(req_struct, "name", "request"),
            "sealed": getattr(req_struct, "deprecated", False) is not None and getattr(req_struct, "alignment_requirement", None) is not None and "@sealed" in getattr(req_struct, "name", "") or getattr(req_struct, "alignment_requirement", None) is not None,
            # note: reliable 'sealed' flag is not always present as boolean attribute in pydsdl repr;
            # we still include it but it might need to be read from the original file if you need exact directive parsing.
            "fields": extract_fields(getattr(req_struct, "fields", [])),
            "constants": extract_constants(getattr(req_struct, "constants", [])),
        }

        service_dict["response"] = {
            "name": getattr(res_struct, "name", "response"),
            "sealed": getattr(res_struct, "deprecated", False) is not None and getattr(res_struct, "alignment_requirement", None) is not None and "@sealed" in getattr(res_struct, "name", "") or getattr(res_struct, "alignment_requirement", None) is not None,
            "fields": extract_fields(getattr(res_struct, "fields", [])),
            "constants": extract_constants(getattr(res_struct, "constants", [])),
        }

        return service_dict

    else:
        # treat as a message / structure
        # top should be StructureType-like
        msg = {
            "kind": "message",
            "name": getattr(top, "name", str(top)),
            "sealed": getattr(top, "deprecated", False) is not None and getattr(top, "alignment_requirement", None) is not None and "@sealed" in getattr(top, "name", "") or getattr(top, "alignment_requirement", None) is not None,
            "fields": extract_fields(getattr(top, "fields", [])),
            "constants": extract_constants(getattr(top, "constants", [])),
        }
        return msg

# ----------------------
# CLI entrypoint
# ----------------------

def main(argv):
    if len(argv) < 3:
        print("Usage: python dsdl_inspect.py /path/to/Type.1.0.dsdl /path/to/root_namespace_dir")
        sys.exit(1)

    dsdl_path = Path(argv[1]).resolve()
    root_ns = Path(argv[2]).resolve()

    try:
        result = parse_dsdl_file(dsdl_path, root_ns)
    except Exception as exc:
        print("Error parsing DSDL:", exc, file=sys.stderr)
        sys.exit(2)

    # print machine-readable dictionary (optional):
    # import json; print(json.dumps(result, indent=2))

    # pretty print:
    # pretty_print(result)
    pprint.pprint(result, sort_dicts=False)

if __name__ == "__main__":
    main(sys.argv)
