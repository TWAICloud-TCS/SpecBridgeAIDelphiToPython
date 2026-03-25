#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, re
from pathlib import Path
from typing import Tuple, List, Dict, Any


def read_text_best_effort(
    path: Path,
    candidates=("utf-8-sig", "utf-8", "cp950", "big5", "big5hkscs", "cp1252", "latin1"),
) -> Tuple[str, str]:
    b = Path(path).read_bytes()
    for enc in candidates:
        try:
            return b.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return b.decode("latin1", errors="replace"), "latin1(replace)"


def is_binary_dfm(b: bytes) -> bool:
    # TPF0/TPF3 may not be at offset 0; allow some slack
    return (
        b.startswith(b"TPF0")
        or b.startswith(b"TPF3")
        or (b.find(b"TPF0") != -1)
        or (b.find(b"TPF3") != -1)
    )


def unescape_pascal_string(s: str) -> str:
    return s.replace("''", "'")


def parse_char_codes(s: str) -> str:
    def repl(m):
        try:
            return chr(int(m.group(1)))
        except Exception:
            return ""

    return re.sub(r"#(\d+)", repl, s)


def set_nested_prop(props: Dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    cur = props
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    last = parts[-1]
    if last in cur and isinstance(cur[last], dict) and isinstance(value, dict):
        cur[last].update(value)
    else:
        cur[last] = value


def parse_string_literal(token: str) -> str:
    assert token.startswith("'") and token.endswith("'")
    inner = token[1:-1]
    inner = unescape_pascal_string(inner)
    inner = parse_char_codes(inner)
    return inner


def parse_scalar_value(token: str) -> Any:
    if token in ("True", "False"):
        return token == "True"
    if token.lower() == "nil":
        return None
    try:
        if token.startswith("0x") or token.startswith("$"):
            return int(token.replace("$", "0x"), 16)
        if re.fullmatch(r"[+-]?\d+", token):
            return int(token)
        if re.fullmatch(r"[+-]?\d+\.\d*", token):
            return float(token)
    except Exception:
        pass
    if token.startswith("'") and token.endswith("'"):
        return parse_string_literal(token)
    return token


def parse_parenthesized_strings(lines: List[str], i: int):
    items = []
    i += 1
    while i < len(lines):
        line = lines[i].strip()
        if line == ")":
            return items, i + 1
        pos = 0
        cur = ""
        while pos < len(line):
            if line[pos] == "'":
                pos2 = pos + 1
                while pos2 < len(line):
                    if line[pos2] == "'" and (
                        pos2 + 1 >= len(line) or line[pos2 + 1] != "'"
                    ):
                        break
                    elif (
                        line[pos2] == "'"
                        and pos2 + 1 < len(line)
                        and line[pos2 + 1] == "'"
                    ):
                        pos2 += 2
                        continue
                    pos2 += 1
                token = line[pos : pos2 + 1]
                cur += parse_string_literal(token)
                pos = pos2 + 1
            elif line[pos] == "#":
                m = re.match(r"#(\d+)", line[pos:])
                if m:
                    cur += chr(int(m.group(1)))
                    pos += len(m.group(0))
                else:
                    pos += 1
            else:
                pos += 1
        if cur != "":
            items.append(cur)
        i += 1
    raise ValueError("Unclosed TStrings '(' block")


def parse_set_or_list_inside_parentheses(rhs: str, lines: List[str], i: int):
    if "'" in rhs:
        return parse_parenthesized_strings(lines, i)
    buf = rhs
    depth = rhs.count("(") - rhs.count(")")
    j = i + 1
    while depth > 0 and j < len(lines):
        buf += " " + lines[j].strip()
        depth += lines[j].count("(") - lines[j].count(")")
        j += 1
    inner = buf.strip()
    if inner.startswith("(") and inner.endswith(")"):
        inner = inner[1:-1]
    items = [t.strip() for t in inner.split(",") if t.strip() != ""]
    parsed = [
        parse_scalar_value(t) if re.fullmatch(r"[+-]?\d+(\.\d*)?", t) else t
        for t in items
    ]
    return parsed, j


def parse_binary_blob(lines: List[str], i: int):
    line = lines[i]
    start = line.find("{")
    buf = line[start:]
    depth = line.count("{") - line.count("}")
    j = i + 1
    while depth > 0 and j < len(lines):
        buf += " " + lines[j]
        depth += lines[j].count("{") - lines[j].count("}")
        j += 1
    hex_str = re.sub(r"[^0-9A-Fa-f]", "", buf)
    return {"__binary_hex": hex_str}, j


def parse_collection(lines: List[str], i: int):
    items = []
    j = i
    if "<" not in lines[j]:
        j += 1
    j += 1
    while j < len(lines):
        s = lines[j].strip()
        if s == ">":
            return items, j + 1
        if s.startswith("item"):
            j += 1
            props = {}
            while j < len(lines):
                t = lines[j].strip()
                if t == "end":
                    items.append(props)
                    j += 1
                    break
                if "=" in t:
                    key, rhs = t.split("=", 1)
                    key = key.strip()
                    rhs = rhs.strip()
                    if rhs.startswith("("):
                        val, j = parse_set_or_list_inside_parentheses(rhs, lines, j)
                    elif rhs.startswith("<"):
                        lines[j] = key + " = <"
                        val, j = parse_collection(lines, j)
                    elif rhs.startswith("{"):
                        val, j = parse_binary_blob(lines, j)
                    else:
                        val = parse_scalar_value(rhs)
                        j += 1
                    set_nested_prop(props, key, val)
                else:
                    j += 1
        else:
            j += 1
    raise ValueError("Unclosed collection '<' block")


def parse_object(lines: List[str], i: int):
    header = lines[i].strip()
    kind = "object"
    if header.startswith("inherited"):
        kind = "inherited"
        header = header[len("inherited") :].strip()
    elif header.startswith("inline"):
        kind = "inline"
        header = header[len("inline") :].strip()
    elif header.startswith("object"):
        header = header[len("object") :].strip()
    m = re.match(r"([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*)", header)
    if not m:
        raise ValueError(f"Cannot parse object header: {lines[i]}")
    name, klass = m.group(1), m.group(2)
    node = {"kind": kind, "name": name, "class": klass, "props": {}, "children": []}
    i += 1
    while i < len(lines):
        s = lines[i].strip()
        if s == "end":
            return node, i + 1
        if not s:
            i += 1
            continue
        if s.startswith(("object ", "inherited ", "inline ")):
            child, i = parse_object(lines, i)
            node["children"].append(child)
            continue
        if "=" in s:
            key, rhs = s.split("=", 1)
            key = key.strip()
            rhs = rhs.strip()
            if rhs.startswith("("):
                val, i = parse_set_or_list_inside_parentheses(rhs, lines, i)
            elif rhs.startswith("<"):
                lines[i] = f"{key} = <"
                val, i = parse_collection(lines, i)
            elif rhs.startswith("{"):
                val, i = parse_binary_blob(lines, i)
            else:
                val = parse_scalar_value(rhs)
                i += 1
            set_nested_prop(node["props"], key, val)
        else:
            i += 1
    raise ValueError("Unclosed object 'end' block")


def extract_ascii_strings(b: bytes, min_len: int = 4):
    return re.findall(rb"[\x20-\x7E]{%d,}" % min_len, b)


def extract_utf16le_ascii_strings(b: bytes, min_chars: int = 4):
    patt = re.compile((rb"(?:[\x20-\x7E]\x00){%d,}" % min_chars))
    out = []
    for m in patt.finditer(b):
        try:
            out.append(m.group(0).decode("utf-16le"))
        except Exception:
            pass
    return out


def extract_cp950_runs(b: bytes, min_chars: int = 4):
    out = []
    i = 0
    n = len(b)
    cur = bytearray()

    def flush():
        nonlocal cur
        if len(cur) >= min_chars:
            try:
                s = bytes(cur).decode("cp950")
            except Exception:
                s = bytes(cur).decode("cp950", errors="ignore")
            s = s.strip()
            if len(s) >= min_chars:
                out.append(s)
        cur = bytearray()

    while i < n:
        x = b[i]
        if 0x20 <= x <= 0x7E:
            cur.append(x)
            i += 1
        elif 0x81 <= x <= 0xFE and i + 1 < n:
            y = b[i + 1]
            if (0x40 <= y <= 0x7E) or (0xA1 <= y <= 0xFE):
                cur.extend([x, y])
                i += 2
            else:
                flush()
                i += 1
        elif x in (0x0D, 0x0A, 0x09, 0x20):
            if cur and cur[-1] != 0x20:
                cur.append(0x20)
            i += 1
        else:
            flush()
            i += 1
    flush()
    # dedup preserve order
    seen = set()
    uniq = []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def parse_dfm_text_to_json(path: Path) -> Dict[str, Any]:
    b = path.read_bytes()
    if is_binary_dfm(b):
        raise ValueError(
            "Binary DFM detected (TPF0/TPF3). Convert to Text DFM first (Alt+F12 / View as Text)."
        )
    text, enc = read_text_best_effort(path)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    while i < len(lines) and not lines[i].lstrip().startswith(
        ("object ", "inherited ", "inline ")
    ):
        i += 1
    if i >= len(lines):
        raise ValueError("No 'object/inherited/inline' found; not a valid Text DFM?")
    root, j = parse_object(lines, i)
    return {"_meta": {"encoding": enc, "source": str(path)}, "root": root}


def salvage_binary_dfm_to_json(path: Path) -> Dict[str, Any]:
    b = path.read_bytes()
    ascii_s = [s.decode("ascii", errors="ignore") for s in extract_ascii_strings(b, 4)]
    utf16_s = extract_utf16le_ascii_strings(b, 4)
    cp950_s = extract_cp950_runs(b, 4)

    def clean(lst):
        cleaned = []
        seen = set()
        for s in lst:
            t = re.sub(r"\s{2,}", " ", s.strip())
            if t and t not in seen:
                seen.add(t)
                cleaned.append(t)
        return cleaned

    return {
        "_meta": {"binary": True, "source": str(path)},
        "strings": {
            "ascii": clean(ascii_s),
            "utf16le": clean(utf16_s),
            "cp950": clean(cp950_s),
        },
    }


def main(argv: List[str]) -> None:
    import argparse

    ap = argparse.ArgumentParser(
        description="Convert Text DFM to JSON (with optional salvage for Binary DFM)"
    )
    ap.add_argument("input", help="Input .dfm")
    ap.add_argument("-o", "--output", help="Output .json (defaults to input.json)")
    ap.add_argument(
        "--salvage",
        action="store_true",
        help="If input is Binary DFM, output strings-only JSON instead of failing",
    )
    args = ap.parse_args(argv)
    in_path = Path(args.input)
    if not in_path.exists():
        raise SystemExit(f"Input not found: {in_path}")
    b = in_path.read_bytes()
    if is_binary_dfm(b):
        if not args.salvage:
            raise SystemExit(
                "Binary DFM detected. Convert to Text DFM first, or rerun with --salvage to dump strings JSON."
            )
        data = salvage_binary_dfm_to_json(in_path)
    else:
        data = parse_dfm_text_to_json(in_path)
    out_path = Path(args.output) if args.output else in_path.with_suffix(".json")
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote: {out_path}")
