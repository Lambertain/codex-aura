"""Rule-based impact analysis engine for predicting affected files."""

import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple


class DependencyAnalyzer:
    """Analyzes Python files for dependencies using AST."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self._deps_cache: Dict[str, Dict[str, Set[str]]] = {}
        self._defs_cache: Dict[str, Dict[str, Set[str]]] = {}

    def get_dependencies(self, file_path: str) -> Dict[str, Set[str]]:
        """Get dependencies (imports, calls, extends) for a file."""
        if file_path in self._deps_cache:
            return self._deps_cache[file_path]

        full_path = self.repo_path / file_path
        if not full_path.exists():
            return {'imports': set(), 'calls': set(), 'extends': set()}

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return {'imports': set(), 'calls': set(), 'extends': set()}

        deps = self._analyze_dependencies(content)
        self._deps_cache[file_path] = deps
        return deps

    def get_definitions(self, file_path: str) -> Dict[str, Set[str]]:
        """Get definitions (functions, classes) in a file."""
        if file_path in self._defs_cache:
            return self._defs_cache[file_path]

        full_path = self.repo_path / file_path
        if not full_path.exists():
            return {'functions': set(), 'classes': set()}

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return {'functions': set(), 'classes': set()}

        defs = self._analyze_definitions(content)
        self._defs_cache[file_path] = defs
        return defs

    def _analyze_dependencies(self, content: str) -> Dict[str, Set[str]]:
        """Analyze file dependencies using AST."""
        imports = set()
        calls = set()
        extends = set()

        try:
            tree = ast.parse(content)
            analyzer = _DependencyVisitor()
            analyzer.visit(tree)
            imports = analyzer.imports
            calls = analyzer.calls
            extends = analyzer.extends
        except SyntaxError:
            pass

        return {
            'imports': imports,
            'calls': calls,
            'extends': extends
        }

    def _analyze_definitions(self, content: str) -> Dict[str, Set[str]]:
        """Analyze file definitions using AST."""
        functions = set()
        classes = set()

        try:
            tree = ast.parse(content)
            analyzer = _DefinitionVisitor()
            analyzer.visit(tree)
            functions = analyzer.functions
            classes = analyzer.classes
        except SyntaxError:
            pass

        return {
            'functions': functions,
            'classes': classes
        }


class _DependencyVisitor(ast.NodeVisitor):
    """AST visitor to collect dependencies."""

    def __init__(self):
        self.imports: Set[str] = set()
        self.calls: Set[str] = set()
        self.extends: Set[str] = set()
        self.current_class = None

    def visit_Import(self, node: ast.Import):
        """Collect import statements."""
        for alias in node.names:
            self.imports.add(alias.name.split('.')[0])
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Collect from import statements."""
        if node.module:
            self.imports.add(node.module.split('.')[0])
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        """Collect class inheritance."""
        self.current_class = node.name
        for base in node.bases:
            if isinstance(base, ast.Name):
                self.extends.add(base.id)
            elif isinstance(base, ast.Attribute):
                # Handle qualified names like module.Class
                self.extends.add(base.attr)
        self.generic_visit(node)
        self.current_class = None

    def visit_Call(self, node: ast.Call):
        """Collect function calls."""
        if isinstance(node.func, ast.Name):
            self.calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            # Handle method calls like obj.method()
            if isinstance(node.func.value, ast.Name):
                # For simplicity, collect the method name
                self.calls.add(node.func.attr)
        self.generic_visit(node)


class _DefinitionVisitor(ast.NodeVisitor):
    """AST visitor to collect definitions."""

    def __init__(self):
        self.functions: Set[str] = set()
        self.classes: Set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Collect function definitions."""
        self.functions.add(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Collect async function definitions."""
        self.functions.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        """Collect class definitions."""
        self.classes.add(node.name)
        self.generic_visit(node)


class ImpactEngine:
    """Rule-based impact analysis engine."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.analyzer = DependencyAnalyzer(str(repo_path))
        self._reverse_deps_cache: Dict[str, Dict[str, List[str]]] = {}

    def predict(self, file_path: str, repo_id: str) -> List[str]:
        """Predict files impacted by changes to file_path.

        Args:
            file_path: Path to the changed file (relative to repo root)
            repo_id: Repository identifier (currently unused, for future multi-repo support)

        Returns:
            Sorted list of impacted file paths
        """
        impacted = set()
        self._collect_impacted(file_path, impacted, depth=0, max_depth=3)

        # Remove the original file from impacted list
        impacted.discard(file_path)

        # Sort for deterministic output
        result = sorted(impacted)
        return result

    def _collect_impacted(self, file_path: str, impacted: Set[str], depth: int, max_depth: int):
        """Recursively collect impacted files."""
        if depth > max_depth or file_path in impacted:
            return

        impacted.add(file_path)

        if depth == max_depth:
            return

        # Get what this file defines
        defs = self.analyzer.get_definitions(file_path)

        # Rule 1: If file imports X → change X affects file
        # Find files that import modules defined in this file
        for module_name in self._get_module_names(file_path):
            importing_files = self._find_files_importing_module(module_name)
            for f in importing_files:
                self._collect_impacted(f, impacted, depth + 1, max_depth)

        # Rule 2: If function A calls B → change A affects B
        # Find files that call functions defined in this file
        for func in defs['functions']:
            calling_files = self._find_files_calling_function(func)
            for f in calling_files:
                self._collect_impacted(f, impacted, depth + 1, max_depth)

        # Rule 3: If class extends Y → change Y affects class
        # Find files that have classes extending classes defined in this file
        for cls in defs['classes']:
            extending_files = self._find_files_extending_class(cls)
            for f in extending_files:
                self._collect_impacted(f, impacted, depth + 1, max_depth)

    def _get_module_names(self, file_path: str) -> List[str]:
        """Get possible module names for a file."""
        # Simple heuristic: filename without .py, and parent directories
        parts = file_path.replace('.py', '').split('/')
        module_names = []
        for i in range(len(parts)):
            module_names.append('.'.join(parts[i:]))
        return module_names

    def _find_files_importing_module(self, module: str) -> List[str]:
        """Find files that import the given module."""
        cache_key = f"import_{module}"
        if cache_key in self._reverse_deps_cache:
            return self._reverse_deps_cache[cache_key]

        files = []
        for root, dirs, filenames in os.walk(self.repo_path):
            for filename in filenames:
                if filename.endswith('.py'):
                    file_path = os.path.relpath(os.path.join(root, filename), self.repo_path)
                    deps = self.analyzer.get_dependencies(file_path)
                    if module in deps['imports']:
                        files.append(file_path)

        self._reverse_deps_cache[cache_key] = files
        return files

    def _find_files_calling_function(self, func: str) -> List[str]:
        """Find files that call the given function."""
        cache_key = f"call_{func}"
        if cache_key in self._reverse_deps_cache:
            return self._reverse_deps_cache[cache_key]

        files = []
        for root, dirs, filenames in os.walk(self.repo_path):
            for filename in filenames:
                if filename.endswith('.py'):
                    file_path = os.path.relpath(os.path.join(root, filename), self.repo_path)
                    deps = self.analyzer.get_dependencies(file_path)
                    if func in deps['calls']:
                        files.append(file_path)

        self._reverse_deps_cache[cache_key] = files
        return files

    def _find_files_extending_class(self, class_name: str) -> List[str]:
        """Find files that have classes extending the given class."""
        cache_key = f"extend_{class_name}"
        if cache_key in self._reverse_deps_cache:
            return self._reverse_deps_cache[cache_key]

        files = []
        for root, dirs, filenames in os.walk(self.repo_path):
            for filename in filenames:
                if filename.endswith('.py'):
                    file_path = os.path.relpath(os.path.join(root, filename), self.repo_path)
                    deps = self.analyzer.get_dependencies(file_path)
                    if class_name in deps['extends']:
                        files.append(file_path)

        self._reverse_deps_cache[cache_key] = files
        return files