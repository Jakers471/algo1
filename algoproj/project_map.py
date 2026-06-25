"""
Map the project: folder tree, per-file line counts, functions/classes, and
DEPENDENCIES (external pip packages + internal module imports). Stdlib only.

Usage:
    python project_map.py                # map this folder (algoproj)
    python project_map.py <path>         # map a different folder
    python project_map.py . --imports    # also show each file's imports inline
    python project_map.py . --all        # include normally-skipped dirs
"""
import ast
import os
import sys

SKIP = {".git", ".venv", ".venv311", "__pycache__", "node_modules", "bin", "obj",
        ".streamlit", ".vs", ".vscode", ".idea"}
STDLIB = set(getattr(sys, "stdlib_module_names", set()))

ext_used = {}        # package -> set(files)
internal_edges = {}  # file -> set(internal modules)


def _parse(path):
    try:
        return ast.parse(open(path, encoding="utf-8", errors="ignore").read())
    except Exception:
        return None


def defs(tree):
    if tree is None:
        return []
    out = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(n.name + "()")
        elif isinstance(n, ast.ClassDef):
            meths = [m.name for m in n.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
            out.append(f"class {n.name}{{{', '.join(meths)}}}" if meths else f"class {n.name}")
    return out


def imports(tree):
    if tree is None:
        return set()
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                names.add(a.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            if n.level:                       # relative import = internal
                names.add(".")
            elif n.module:
                names.add(n.module.split(".")[0])
    return names


def lines(path):
    try:
        return sum(1 for _ in open(path, encoding="utf-8", errors="ignore"))
    except Exception:
        return 0


def walk(root, internal_set, show_all, show_imports):
    total_lines = total_py = 0
    for dirpath, dirnames, filenames in os.walk(root):
        if not show_all:
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP and not d.startswith("."))
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        indent = "  " * depth
        if rel != ".":
            print(f"{indent}{os.path.basename(dirpath)}/")
        for f in sorted(filenames):
            p = os.path.join(dirpath, f)
            if f.endswith(".py"):
                tree = _parse(p)
                ln = lines(p); total_lines += ln; total_py += 1
                ds = defs(tree)
                relf = os.path.relpath(p, root).replace(os.sep, "/")
                imps = imports(tree)
                internal = sorted(m for m in imps if m == "." or m in internal_set)
                internal = ["(relative)" if m == "." else m for m in internal]
                external = sorted(m for m in imps if m != "." and m not in internal_set and m not in STDLIB)
                for e in external:
                    ext_used.setdefault(e, set()).add(relf)
                if internal:
                    internal_edges[relf] = internal
                names = ("  ::  " + ", ".join(ds)) if ds else ""
                print(f"{indent}  {f:<26} {ln:>5} ln{names}")
                if show_imports and (external or internal):
                    dep = []
                    if external:
                        dep.append("ext[" + ", ".join(external) + "]")
                    if internal:
                        dep.append("int[" + ", ".join(internal) + "]")
                    print(f"{indent}      deps: " + "  ".join(dep))
            elif f.endswith((".md", ".toml", ".json", ".bat", ".ipynb", ".csv")):
                print(f"{indent}  {f:<26} {lines(p):>5} ln")
    print(f"\nTOTAL: {total_py} .py files, {total_lines} lines of Python")


def summaries():
    if ext_used:
        print("\nEXTERNAL DEPENDENCIES (third-party / pip):")
        for pkg in sorted(ext_used):
            print(f"  {pkg:<16} used by {len(ext_used[pkg])} file(s)")
    if internal_edges:
        print("\nINTERNAL DEPENDENCIES (file -> internal modules):")
        for f in sorted(internal_edges):
            print(f"  {f:<34} -> {', '.join(internal_edges[f])}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = os.path.abspath(args[0]) if args else os.path.dirname(os.path.abspath(__file__))
    internal_set = {"algokit", "app", "strategies", "config", "nbtools", "views", "research", "viz"}
    for name in os.listdir(root):
        if os.path.isdir(os.path.join(root, name)):
            internal_set.add(name)
        elif name.endswith(".py"):
            internal_set.add(name[:-3])
    print(f"# {root}\n")
    walk(root, internal_set, "--all" in sys.argv, "--imports" in sys.argv)
    summaries()
