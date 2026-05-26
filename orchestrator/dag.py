"""
DAG and Task primitives.

A `Task` wraps a callable plus a list of upstream task names. A `DAG`
holds an ordered set of tasks; topological order is resolved at run
time via Kahn's algorithm so cycles raise loudly instead of looping
forever.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Task:
    name: str
    fn: Callable[[dict], dict | None]
    depends_on: list[str] = field(default_factory=list)


@dataclass
class DAG:
    name: str
    tasks: list[Task]

    def task_map(self) -> dict[str, Task]:
        return {t.name: t for t in self.tasks}

    def topological_order(self) -> list[str]:
        """Kahn's algorithm. Raises ValueError on cycles or missing deps."""
        names = {t.name for t in self.tasks}
        indegree = {t.name: 0 for t in self.tasks}
        adj: dict[str, list[str]] = {t.name: [] for t in self.tasks}

        for t in self.tasks:
            for dep in t.depends_on:
                if dep not in names:
                    raise ValueError(f'task {t.name!r} depends on unknown {dep!r}')
                adj[dep].append(t.name)
                indegree[t.name] += 1

        ordered: list[str] = []
        ready = [n for n, d in indegree.items() if d == 0]

        while ready:
            ready.sort()  # deterministic ordering for stable state files
            n = ready.pop(0)
            ordered.append(n)
            for downstream in adj[n]:
                indegree[downstream] -= 1
                if indegree[downstream] == 0:
                    ready.append(downstream)

        if len(ordered) != len(self.tasks):
            raise ValueError(f'cycle detected in DAG {self.name!r}')
        return ordered


# --- DAG registry -----------------------------------------------------

_registry: dict[str, DAG] = {}


def register_dag(dag: DAG) -> DAG:
    if dag.name in _registry:
        raise ValueError(f'duplicate DAG name {dag.name!r}')
    _registry[dag.name] = dag
    return dag


def get_dag(name: str) -> DAG:
    if name not in _registry:
        # Lazy import so registering a new DAG file is the only step.
        from .dags import load_all_dags  # noqa: WPS433 (local import is deliberate)
        load_all_dags()

    if name not in _registry:
        raise KeyError(f'no DAG named {name!r}; known: {sorted(_registry)}')
    return _registry[name]


def known_dags() -> list[str]:
    from .dags import load_all_dags
    load_all_dags()
    return sorted(_registry)
