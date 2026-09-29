"""
Architecture Compliance Tests.
Enforces Part A Fifth Absolute Rule:
The decision engine MUST NOT import simulator or simulator-specific modules.
"""

import os
import ast
import pytest


def get_python_files(directory: str):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                yield os.path.join(root, file)


def test_decision_engine_never_imports_simulator():
    """
    Scans all Python files in decision_engine/ and asserts no imports from simulator.
    """
    decision_engine_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "decision_engine"))
    assert os.path.exists(decision_engine_dir), "decision_engine directory must exist"

    violations = []

    for file_path in get_python_files(decision_engine_dir):
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "simulator" or alias.name.startswith("simulator."):
                        violations.append(f"{file_path}:{node.lineno} imports '{alias.name}'")
            elif isinstance(node, ast.ImportFrom):
                if node.module == "simulator" or (node.module and node.module.startswith("simulator.")):
                    violations.append(f"{file_path}:{node.lineno} imports from '{node.module}'")

    assert not violations, f"Architecture violation: decision_engine imports from simulator:\n" + "\n".join(violations)


def test_failure_injections_never_call_recovery():
    """
    Part I Rule: Failure injection methods MUST ONLY modify simulated conditions.
    They must never directly call recovery methods (hover, return_to_home, relocate, etc.).
    """
    drone_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "simulator", "drone.py"))
    with open(drone_file, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=drone_file)

    forbidden_calls = {"command_hover", "command_relocate", "command_return_to_home",
                       "command_alternate_route", "command_emergency_landing", "command_resume_mission"}

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("inject_"):
            for subnode in ast.walk(node):
                if isinstance(subnode, ast.Call):
                    func_name = None
                    if isinstance(subnode.func, ast.Name):
                        func_name = subnode.func.id
                    elif isinstance(subnode.func, ast.Attribute):
                        func_name = subnode.func.attr

                    if func_name in forbidden_calls:
                        violations.append(f"{node.name} calls forbidden recovery method '{func_name}'")

    assert not violations, f"Part I violation: injection method directly calls recovery:\n" + "\n".join(violations)

