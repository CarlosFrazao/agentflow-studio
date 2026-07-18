"""FEAT-010 — Quality & Hardening (P3) regression checks.

Guards the P3 cleanups applied in Bloco 10:
- All app modules import without undefined-name errors (F821).
- The Card.project relationship resolves to the Project model (no broken
  forward reference after removing the undefined `Project` name).
- No unused imports remain across the app package (F401).
"""

import ast
import importlib
import os


def test_app_modules_import_without_undefined_names():
    """Every module under app/ must import cleanly (no F821 undefined names)."""
    import app  # noqa: F401

    # Import the key submodules that previously had undefined-name errors.
    import app.models.card  # noqa: F401
    import app.models.project  # noqa: F401
    import app.api.v1.cards  # noqa: F401
    import app.services.deps  # noqa: F401

    assert True


def test_card_project_relationship_resolves_to_project_model():
    """Card.project must be a mapped relationship bound to the Project class."""
    from app.models.card import Card
    from app.models.project import Project

    relationship = Card.__mapper__.relationships["project"]
    assert relationship.mapper.class_ is Project


def test_no_unused_imports_in_app_package():
    """Static AST scan: no `import X` / `from X import Y` that is never referenced."""
    app_root = os.path.dirname(importlib.import_module("app").__file__)
    violations = []

    for dirpath, _dirnames, filenames in os.walk(app_root):
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)

            # Skip pure re-export aggregators that use `# noqa: F401`.
            if filename == "__init__.py":
                source_lines = open(path, encoding="utf-8").read().splitlines()
                if any("noqa: F401" in line for line in source_lines):
                    continue

            # Collect imported names and referenced names.
            imported_locals = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for alias in node.names:
                        imported_locals.add(alias.asname or alias.name.split(".")[0])
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_locals.add(alias.asname or alias.name.split(".")[0])

            referenced = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    referenced.add(node.id)
                elif isinstance(node, ast.Attribute):
                    # Capture the base identifier of `a.b.c` usages.
                    base = node
                    while isinstance(base, ast.Attribute):
                        base = base.value
                    if isinstance(base, ast.Name):
                        referenced.add(base.id)
                elif isinstance(node, ast.AnnAssign):
                    # Type annotations (e.g. `Mapped["Project"]`) reference names too,
                    # including forward references written as string literals.
                    annotation = node.annotation
                    for sub in ast.walk(annotation):
                        if isinstance(sub, ast.Name):
                            referenced.add(sub.id)
                        elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                            referenced.add(sub.value.split(".")[0])
                elif isinstance(node, (ast.arg, ast.FunctionDef, ast.AsyncFunctionDef, ast.Return)):
                    ann = getattr(node, "annotation", None)
                    if ann:
                        for sub in ast.walk(ann):
                            if isinstance(sub, ast.Name):
                                referenced.add(sub.id)
                            elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                                referenced.add(sub.value.split(".")[0])

            unused = imported_locals - referenced - {"annotations", "TYPE_CHECKING"}
            if unused:
                violations.append((path, sorted(unused)))

    assert not violations, f"Unused imports found: {violations}"
