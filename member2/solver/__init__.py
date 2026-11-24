"""Solver backends. A backend that cannot be loaded on this machine is skipped, never faked."""
from importlib import import_module

BACKENDS = ("ortools", "pulp")


class SolverUnavailable(RuntimeError):
    pass


def load_backend(name):
    """ImportError: package missing. OSError: the operating system refused its native library."""
    try:
        return import_module(f".{name}_solver", __package__)
    except (ImportError, OSError) as error:
        raise SolverUnavailable(f"{name}: {error}") from error


def first_available(preferred):
    """(name, module) for the preferred backend, or the other one when it cannot be loaded."""
    errors = []
    for name in sorted(BACKENDS, key=lambda n: n != preferred):
        try:
            return name, load_backend(name)
        except SolverUnavailable as error:
            errors.append(str(error))
    raise SolverUnavailable("; ".join(errors))
