"""Versioned JSON Schema validation for the hmem pilot.

Uses `jsonschema` when available; otherwise falls back to a documented
standard-library validator that covers the keyword subset our schemas use
(type, properties, required, additionalProperties, items, minItems, enum,
const, pattern, minimum, maximum). Payloads must carry a schema_version of the
form "<kind>@<version>" matching the registered schema document version.
"""
import glob
import json
import os
import re

from . import SCHEMA_VERSIONS

DEFAULT_SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schemas")
DEFAULT_SCENARIOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios")

try:  # prefer the real validator when present
    import jsonschema as _jsonschema  # noqa: F401
    _HAS_JSONSCHEMA = True
except Exception:  # pragma: no cover - exercised on clean machines without it
    _jsonschema = None
    _HAS_JSONSCHEMA = False


def _type_ok(value, type_spec):
    if type_spec == "object":
        return isinstance(value, dict)
    if type_spec == "array":
        return isinstance(value, list)
    if type_spec == "string":
        return isinstance(value, str)
    if type_spec == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_spec == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_spec == "boolean":
        return isinstance(value, bool)
    if type_spec == "null":
        return value is None
    return True  # unknown type keyword: pass through (documented limitation)


def _validate_stdlib(doc, schema, path="$"):
    """Minimal JSON Schema (draft-07 subset) validator, standard library only."""
    errors = []
    if not isinstance(schema, dict):
        return errors
    if "type" in schema:
        specs = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(doc, s) for s in specs):
            errors.append(f"{path}: expected type {schema['type']}, got {type(doc).__name__}")
            return errors
    if isinstance(doc, dict):
        for key in schema.get("required", []):
            if key not in doc:
                errors.append(f"{path}: missing required property '{key}'")
        for key, value in doc.items():
            if key in schema.get("properties", {}):
                errors += _validate_stdlib(value, schema["properties"][key], f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: additional property '{key}' not allowed")
        # patternProperties is not used by the pilot schemas (documented).
    elif isinstance(doc, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for i, item in enumerate(doc):
                errors += _validate_stdlib(item, items, f"{path}[{i}]")
        if "minItems" in schema and len(doc) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
    if isinstance(doc, (int, float)) and not isinstance(doc, bool):
        if "minimum" in schema and doc < schema["minimum"]:
            errors.append(f"{path}: value {doc} below minimum {schema['minimum']}")
        if "maximum" in schema and doc > schema["maximum"]:
            errors.append(f"{path}: value {doc} above maximum {schema['maximum']}")
    if isinstance(doc, str) and "pattern" in schema:
        if not re.search(schema["pattern"], doc):
            errors.append(f"{path}: string does not match pattern {schema['pattern']!r}")
    if "enum" in schema and doc not in schema["enum"]:
        errors.append(f"{path}: value {doc!r} not in enum {schema['enum']}")
    if "const" in schema and doc != schema["const"]:
        errors.append(f"{path}: value {doc!r} != const {schema['const']!r}")
    return errors


def validate_document(doc, schema):
    """Validate `doc` against a JSON Schema document. Returns list of error strings."""
    if _HAS_JSONSCHEMA and _jsonschema is not None:
        try:
            _jsonschema.validate(instance=doc, schema=schema)
            return []
        except Exception as exc:
            return [str(exc)]
    return _validate_stdlib(doc, schema)


def load_schema_doc(name, schema_dir=DEFAULT_SCHEMA_DIR):
    """Load a schema document by filename; returns dict or None."""
    path = os.path.join(schema_dir, name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def schema_errors_for_dir(schema_dir=DEFAULT_SCHEMA_DIR):
    """Validate that every *.schema.json in the dir is well-formed and registered."""
    errors = {}
    for name, (_doc, _ver) in SCHEMA_VERSIONS.items():
        doc = load_schema_doc(_doc, schema_dir)
        if doc is None:
            errors[_doc] = ["schema document missing"]
        elif doc.get("version") != _ver:
            errors[_doc] = [f"document version {doc.get('version')!r} != registered {_ver!r}"]
        elif not isinstance(doc, dict) or doc.get("type") != "object":
            errors[_doc] = ["schema document must be a JSON object of type object"]
    return errors


def validate_payload(payload, kind, schema_dir=DEFAULT_SCHEMA_DIR):
    """Validate a versioned payload of `kind` against its registered schema.

    Checks schema_version first (kind@version must match the registered
    schema document version), then validates the document.
    """
    if kind not in SCHEMA_VERSIONS:
        return [f"unknown payload kind {kind!r}"]
    doc_name, version = SCHEMA_VERSIONS[kind]
    expected = f"{kind}@{version}"
    errors = []
    got = payload.get("schema_version") if isinstance(payload, dict) else None
    if got != expected:
        errors.append(f"schema_version: expected {expected!r}, got {got!r}")
    schema = load_schema_doc(doc_name, schema_dir)
    if schema is None:
        errors.append(f"schema document {doc_name} not found in {schema_dir}")
        return errors
    if isinstance(payload, dict):
        errors += validate_document(payload, schema)
    return errors


def validate_all_scenarios(scenarios_dir=DEFAULT_SCENARIOS_DIR, schema_dir=DEFAULT_SCHEMA_DIR):
    """Validate every scenario JSON in a directory.

    Returns {"valid": [abs paths], "invalid": {abs path: [errors]}}.
    """
    valid, invalid = [], {}
    for path in sorted(glob.glob(os.path.join(scenarios_dir, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
        except Exception as exc:
            invalid[path] = [f"not valid JSON: {exc}"]
            continue
        errors = validate_payload(doc, "scenario", schema_dir)
        if errors:
            invalid[path] = errors
        else:
            valid.append(path)
    return {"valid": valid, "invalid": invalid}
