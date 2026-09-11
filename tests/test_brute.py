"""Broad module-surface smoke tests.

This file intentionally does not execute every discovered function with fabricated
arguments. Many engine functions perform real filesystem, SQLite, service, or index
work, so arbitrary invocation is both non-deterministic and a poor proxy for
coverage. Behaviour is exercised by the focused tests elsewhere in the suite.
"""

import inspect


def test_engine_module_surfaces_are_importable_and_inspectable():
    """Public Python functions in core engine modules expose valid signatures."""
    from llm_kosh.engine import commands, search, healing, compiler, safety
    from llm_kosh.core import memory, utils

    modules = [commands, search, healing, compiler, safety, memory, utils]

    for module in modules:
        functions = [
            (name, obj)
            for name, obj in inspect.getmembers(module, inspect.isfunction)
            if not name.startswith("_") and obj.__module__ == module.__name__
        ]

        assert functions, f"{module.__name__} exposes no public functions"
        for name, function in functions:
            signature = inspect.signature(function)
            assert signature is not None, f"Could not inspect {module.__name__}.{name}"


def test_index_entry_points_are_exposed():
    """Keep explicit smoke coverage for the index APIs implicated by CI."""
    from llm_kosh.engine import search

    assert callable(search.rebuild_index)
    assert callable(search.build_vector_index)
    assert callable(search.inspect_index)
