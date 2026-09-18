"""Shared I/O for the feature notes: the project memory as markdown notes.

The project scope lives in `features/` as one note per feature, named
`F-<id>_<name>.md`, with flat YAML front matter plus two list-valued fields
(`acceptance`, `tags`). `spec` is a wikilink (`[[REQ-001_name]]`) to the
requirement note in `specs/`.

This module is the single place the harness reads and writes those notes, so
the validator (validate_features.py), the traceability check
(validate_requirements.py), the approver (approve.py) and the bootstrap
(instantiate.py) do not drift apart.

Notes that ship with the template start with `_` and are ignored as features:
`features/_project.md` holds the project metadata and `features/_template.md`
is the copy source for new notes.

The parser deliberately has no external dependencies (the harness does not
install PyYAML). It understands flat `key: value` pairs and list-valued keys
(`acceptance:`) written as indented `- "item"` lines; a feature note is only
allowed lists for `acceptance` and `tags`, but a requirement note stays flat.
"""

from __future__ import annotations

import os
import re
import tempfile

FEATURE_DIR = "features"

# F-001_short_snake_case.md — the id and the name must match the front matter.
FEATURE_FILE_RE = re.compile(r"^F-(\d{3,})_([a-z0-9]+(?:_[a-z0-9]+)*)\.md$")

# What `spec` may point at: the bare requirement name, with or without the
# specs/ prefix and the .md extension.
SPEC_NAME_RE = re.compile(r"^REQ-\d{3}_[a-z0-9]+(?:_[a-z0-9]+)*$")

# A placeholder is a token between angle brackets. It keeps the template notes
# out of the counts without inventing a separate status vocabulary.
PLACEHOLDER_RE = re.compile(r"<[^>]+>")


def parse_frontmatter(text: str) -> tuple[dict, list[str]] | None:
    """Flat YAML front matter with list-valued keys. None if absent/unterminated.

    Returns `(fields, repeated_keys)`. A key may hold a scalar (`key: value`)
    or a list (`key:` followed by indented `- "item"` lines). Values have their
    surrounding quotes stripped; `#` is NOT treated as a comment inside a
    value, because a legitimate title can carry a hash (`Fix bug #123`).

    Deliberately minimal: no PyYAML. In exchange, the note templates keep to
    flat keys plus the two allowed lists.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    fields: dict = {}
    repeated: list[str] = []
    list_key: str | None = None

    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            return fields, repeated

        # Still inside a list: every further indented `- "item"` belongs to the
        # key that opened it. The first non-indented line ends the list.
        if list_key is not None:
            if line[:1] in (" ", "\t"):
                if stripped.startswith("-"):
                    item = stripped[1:].strip().strip("\"'")
                    fields[list_key].append(item)
                continue
            list_key = None

        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            continue

        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip("\"'")
        if not key:
            continue

        if key in fields:
            if list_key is not None:
                continue
            repeated.append(key)
            continue

        if value in ("", "<none>"):
            # An empty value opens a list (`acceptance:`). An empty scalar
            # (`description:` in _project.md) is read the same way: as an empty
            # list, which callers treat as "not filled in" either way.
            list_key = key
            fields[key] = []
            continue

        fields[key] = value

    return None


def _quote(value: str) -> str:
    """Quotes what a flat scalar would otherwise not round-trip."""
    if re.fullmatch(r"[A-Za-z0-9_.\-]+", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def serialize_frontmatter(fields: dict) -> str:
    """The note's front matter block (with the surrounding `---`), as text."""
    lines = ["---"]
    for key, value in fields.items():
        if key.startswith("_"):
            continue
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f'  - "{_quote(str(item))}"')
        else:
            lines.append(f"{key}: {_quote(str(value))}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def write_note(root: str, rel: str, fields: dict, body: str) -> None:
    """Writes the front matter and the body, atomically (temp file + replace).

    `rel` is relative to `root` (e.g. `features/F-001_a_feature.md`). The body
    is preserved verbatim: only the front matter is rebuilt from `fields`.
    """
    path = os.path.join(root, rel).replace("\\", "/")
    content = serialize_frontmatter(fields) + body
    if not content.endswith("\n"):
        content += "\n"
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".note-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def spec_basename(spec: object) -> str | None:
    """The bare requirement name a `spec` value points at, or None.

    Accepts `REQ-001_name`, `REQ-001_name.md`, `specs/REQ-001_name.md`, and
    the Obsidian wikilinks `[[REQ-001_name]]` / `[[REQ-001_name|label]]`.
    """
    if not isinstance(spec, str):
        return None
    value = spec.strip()
    value = value.removeprefix("[[").removesuffix("]]")
    value = value.split("|", 1)[0] if "|" in value else value
    value = value.removeprefix("specs/").removesuffix(".md")
    if not SPEC_NAME_RE.match(value):
        return None
    return value


def feature_files(features_dir: str) -> list[str]:
    """The sorted note file names (not the template's `_*` notes)."""
    if not os.path.isdir(features_dir):
        return []
    return sorted(
        name for name in os.listdir(features_dir)
        if FEATURE_FILE_RE.match(name)
    )


def load_features(root: str) -> tuple[list[dict], list[str]]:
    """Returns (features, format errors).

    Each feature dict carries the front matter fields plus underscore-prefixed
    internals: `_rel` (features/F-..md), `_name` (the file name), `_body` (the
    rest of the note), `_spec` (the raw `spec` value) and `_id`/`_file_id`
    (the integer id from the file name). Notes that fail to parse are reported
    and NOT included: the caller must not judge traceability on a feature it
    could not read.
    """
    features: list[dict] = []
    errors: list[str] = []
    features_dir = os.path.join(root, FEATURE_DIR)
    if not os.path.isdir(features_dir):
        return features, errors

    for name in feature_files(features_dir):
        rel = f"{FEATURE_DIR}/{name}"
        try:
            with open(os.path.join(features_dir, name), encoding="utf-8") as handle:
                content = handle.read()
        except OSError as exc:
            errors.append(f"{rel} cannot be read ({exc}), so it is not loaded")
            continue

        parsed = parse_frontmatter(content)
        if parsed is None:
            errors.append(
                f"{rel}: has no front matter, or it is not closed with ---"
            )
            continue
        fields, repeated = parsed
        if repeated:
            errors.append(
                f"{rel}: the front matter repeats {', '.join(sorted(set(repeated)))}. "
                f"With duplicate keys there is no telling which one counts: keep one"
            )

        match = FEATURE_FILE_RE.match(name)
        assert match is not None
        feature: dict = dict(fields)
        feature["id"] = int(match.group(1))
        feature["name"] = match.group(2)
        feature["_rel"] = rel
        feature["_name"] = name
        feature["_body"] = content.partition("\n---\n")[2]
        feature["_spec"] = fields.get("spec")
        features.append(feature)

    return features, errors