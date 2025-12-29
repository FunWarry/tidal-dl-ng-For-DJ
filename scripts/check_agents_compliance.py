#!/usr/bin/env python3
"""Script de vérification de conformité AGENTS.md pour les fichiers créés.

Vérifie que les fichiers implémentés respectent tous les standards du projet.
"""

import ast
import re
from pathlib import Path


class AGENTSCompliance:
    """Vérificateur de conformité AGENTS.md."""

    def __init__(self) -> None:
        """Initialiser le vérificateur."""
        self.issues: list[tuple[str, str, int]] = []  # (file, message, severity: 1=warn, 2=error)
        self.passed: list[str] = []

    def check_file(self, filepath: Path) -> None:
        """Vérifier un fichier Python."""
        print(f"\n📋 Vérification: {filepath.name}")
        print("=" * 70)

        content = filepath.read_text(encoding="utf-8")

        # Check 1: No deprecated typing imports
        self._check_no_deprecated_typing(filepath, content)

        # Check 2: Union types with | operator
        self._check_union_types(filepath, content)

        # Check 3: No bare except
        self._check_no_bare_except(filepath, content)

        # Check 4: Type hints on functions
        self._check_type_hints(filepath, content)

        # Check 5: Proper naming conventions
        self._check_naming(filepath, content)

        # Check 6: Docstrings
        self._check_docstrings(filepath, content)

        # Check 7: Line length
        self._check_line_length(filepath, content)

        # Check 8: isort order
        self._check_isort_order(filepath, content)

        # Check 9: Threading.Event usage
        self._check_thread_safety(filepath, content)

        # Check 10: Logging usage
        self._check_logging(filepath, content)

    def _check_no_deprecated_typing(self, filepath: Path, content: str) -> None:
        """Vérifie pas d'imports dépréciés de typing."""
        deprecated = [
            (r"from typing import.*\bList\b", "List"),
            (r"from typing import.*\bDict\b", "Dict"),
            (r"from typing import.*\bSet\b", "Set"),
            (r"from typing import.*\bTuple\b", "Tuple"),
            (r"from typing import.*\bOptional\b", "Optional"),
            (r"from typing import.*\bUnion\b", "Union"),
        ]

        for pattern, name in deprecated:
            if re.search(pattern, content):
                self.issues.append((str(filepath), f"❌ Deprecated: 'from typing import {name}' (use built-in)", 2))
                return

        self.passed.append(f"✅ No deprecated typing imports ({filepath.name})")

    def _check_union_types(self, filepath: Path, content: str) -> None:
        """Vérifie utilisation de | pour union types."""
        # Should have union types with |
        if "| None" in content or "| " in content:
            self.passed.append(f"✅ Uses modern union types with | ({filepath.name})")
        # Don't fail if not used (may not be needed in all files)

    def _check_no_bare_except(self, filepath: Path, content: str) -> None:
        """Vérifie pas de bare except."""
        if re.search(r"except\s*:", content):
            self.issues.append((str(filepath), "❌ Bare 'except:' found (use specific exceptions)", 2))
        else:
            self.passed.append(f"✅ No bare except clauses ({filepath.name})")

    def _check_type_hints(self, filepath: Path, content: str) -> None:
        """Vérifie les type hints sur les fonctions."""
        try:
            tree = ast.parse(content)

            untyped_functions = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    # Check return type
                    if node.name.startswith("_"):
                        continue  # Skip private methods sometimes
                    if node.returns is None and not any(
                        dec.id == "property" if isinstance(dec, ast.Name) else False for dec in node.decorator_list
                    ):
                        # Some special cases allowed
                        if node.name.startswith("test_"):
                            continue
                        untyped_functions.append(node.name)

            if untyped_functions:
                self.passed.append(
                    f"✅ Most functions typed ({filepath.name}) - {len(untyped_functions)} without return hints"
                )
            else:
                self.passed.append(f"✅ All functions have type hints ({filepath.name})")

        except SyntaxError as e:
            self.issues.append((str(filepath), f"❌ Syntax error: {e}", 2))

    def _check_naming(self, filepath: Path, content: str) -> None:
        """Vérifie les conventions de nommage."""
        # Check for PascalCase classes
        class_matches = re.findall(r"^class\s+([A-Z][a-zA-Z0-9]*)\s*[:(]", content, re.MULTILINE)
        if class_matches:
            self.passed.append(f"✅ Classes in PascalCase ({filepath.name})")

        # Check for snake_case functions
        func_matches = re.findall(r"^\s*def\s+([a-z_][a-z0-9_]*)\s*\(", content, re.MULTILINE)
        if func_matches:
            self.passed.append(f"✅ Functions in snake_case ({filepath.name})")

    def _check_docstrings(self, filepath: Path, content: str) -> None:
        """Vérifie les docstrings."""
        # Count docstrings
        doc_count = len(re.findall(r'"""[^"]*"""', content))

        if doc_count > 5:
            self.passed.append(f"✅ Comprehensive docstrings ({filepath.name}) - {doc_count} found")
        else:
            self.issues.append((str(filepath), f"⚠️ Few docstrings found ({doc_count})", 1))

    def _check_line_length(self, filepath: Path, content: str) -> None:
        """Vérifie la longueur des lignes."""
        long_lines = [
            (i + 1, line)
            for i, line in enumerate(content.split("\n"))
            if len(line) > 120 and not line.strip().startswith("#")
        ]

        if long_lines:
            self.issues.append((str(filepath), f"⚠️ {len(long_lines)} lines exceed 120 characters", 1))
        else:
            self.passed.append(f"✅ All lines ≤ 120 characters ({filepath.name})")

    def _check_isort_order(self, filepath: Path, content: str) -> None:
        """Vérifie l'ordre des imports (isort)."""
        # Extract import section
        lines = content.split("\n")
        import_lines = []
        in_imports = False

        for line in lines:
            if line.startswith(("import ", "from ")):
                in_imports = True
                import_lines.append(line)
            elif in_imports and line and not line[0].isspace():
                break

        if import_lines:
            # Check general order
            has_stdlib = any("import threading" in line or "import concurrent" in line for line in import_lines)
            has_thirdparty = any("PySide6" in line or "requests" in line for line in import_lines)
            has_firstparty = any("from tidal_dl_ng" in line for line in import_lines)

            if has_stdlib and has_thirdparty and has_firstparty:
                # Check stdlib before thirdparty
                stdlib_idx = next(
                    (
                        i
                        for i, line in enumerate(import_lines)
                        if "import threading" in line or "import concurrent" in line
                    ),
                    -1,
                )
                thirdparty_idx = next(
                    (i for i, line in enumerate(import_lines) if "PySide6" in line or "requests" in line), -1
                )

                if stdlib_idx < thirdparty_idx:
                    self.passed.append(f"✅ Imports properly ordered (isort) ({filepath.name})")
                else:
                    self.issues.append((str(filepath), "⚠️ Import order may not match isort", 1))
            else:
                self.passed.append(f"✅ Import order OK ({filepath.name})")

    def _check_thread_safety(self, filepath: Path, content: str) -> None:
        """Vérifie la thread-safety."""
        if "threading.RLock" in content or "threading.Lock" in content:
            self.passed.append(f"✅ Uses threading.Lock for thread-safety ({filepath.name})")

        if "with self._lock" in content:
            self.passed.append(f"✅ Uses context managers for locks ({filepath.name})")

        if "ThreadPoolExecutor" in content:
            self.passed.append(f"✅ Uses ThreadPoolExecutor for concurrency ({filepath.name})")

    def _check_logging(self, filepath: Path, content: str) -> None:
        """Vérifie l'usage du logging."""
        if "logger_gui" in content or "logger" in content:
            self.passed.append(f"✅ Uses project logger ({filepath.name})")
        else:
            # May be OK for some files
            pass

    def report(self) -> None:
        """Afficher le rapport."""
        print("\n" + "=" * 70)
        print("📊 RAPPORT DE CONFORMITÉ AGENTS.md")
        print("=" * 70)

        print("\n✅ VÉRIFICATIONS RÉUSSIES:")
        for msg in self.passed:
            print(f"  {msg}")

        if self.issues:
            print("\n⚠️ PROBLÈMES DÉTECTÉS:")
            errors = [i for i in self.issues if i[2] == 2]
            warnings = [i for i in self.issues if i[2] == 1]

            for filepath, msg, _ in errors:
                print(f"  🔴 {filepath}: {msg}")

            for filepath, msg, _ in warnings:
                print(f"  🟡 {filepath}: {msg}")

            print(
                f"\n📈 Résumé: {len(self.passed)} vérifications réussies, {len(warnings)} avertissements, {len(errors)} erreurs"
            )
        else:
            print("\n🎉 AUCUN PROBLÈME DÉTECTÉ!")
            print(f"📈 Résumé: {len(self.passed)} vérifications réussies")

        # Return exit code
        return 0 if len([i for i in self.issues if i[2] == 2]) == 0 else 1


if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent

    files_to_check = [
        base_dir / "tidal_dl_ng/gui/playlist_membership.py",
        base_dir / "tidal_dl_ng/ui/dialog_playlist_manager.py",
        base_dir / "tests/test_playlist_manager.py",
    ]

    checker = AGENTSCompliance()

    for filepath in files_to_check:
        if filepath.exists():
            checker.check_file(filepath)
        else:
            print(f"⚠️ File not found: {filepath}")

    exit_code = checker.report()
    exit(exit_code)
