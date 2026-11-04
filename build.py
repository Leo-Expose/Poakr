"""Build the single-file submission bot from src/."""
import argparse
import ast
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCES = ("src/evaluator.py", "src/proofs.py", "src/protocol.py")
HEADER = '''#!/usr/bin/env python3
"""Discard Hold'em protocol 1.0 bot.

Python 3.11; standard library and NumPy only.
No runtime file, network, or process I/O.
"""
import sys, os
sys.dont_write_bytecode = True
for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"
'''


def source_part(name, seen_imports):
    text = (ROOT / name).read_text()
    tree = ast.parse(text)
    remove = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src"):
            remove.update(range(node.lineno, node.end_lineno + 1))
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            remove.update(range(node.lineno, node.end_lineno + 1))
    lines = []
    for number, line in enumerate(text.splitlines(), 1):
        if number in remove:
            continue
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")) and stripped in seen_imports:
            continue
        if stripped.startswith(("import ", "from ")):
            seen_imports.add(stripped)
        lines.append(line)
    return "\n# SOURCE " + name + "\n" + "\n".join(lines).strip() + "\n"


def build(zip_output=False):
    seen_imports = set()
    parts = [HEADER]
    for name in SOURCES:
        parts.append(source_part(name, seen_imports))
    parts.append("\nif __name__ == '__main__':\n    discard_main()\n")
    code = "".join(parts)
    ast.parse(code, feature_version=(3, 11))

    target = ROOT / "bot.py"
    target.write_text(code)
    digest = hashlib.sha256(code.encode()).hexdigest()
    print(f"{target}  {len(code.encode())} bytes  sha256={digest}")

    if zip_output:
        archive = ROOT / "submission.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as handle:
            info = zipfile.ZipInfo("bot.py", date_time=(2026, 11, 15, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            handle.writestr(info, code)
        print(f"{archive}  {archive.stat().st_size} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", action="store_true", help="also create submission.zip")
    build(parser.parse_args().zip)
