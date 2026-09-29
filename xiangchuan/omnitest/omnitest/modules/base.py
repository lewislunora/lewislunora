from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModuleContext:
    target: Any
    options: dict[str, Any]
    reporter: Any
    console: Any
    rng: random.Random = field(default_factory=random.Random)


@dataclass
class ModuleSpec:
    name: str
    heavy: bool = False          # requires authorization gate
    needs_browser: bool = False  # requires selenium/chrome
    help: str = ""


MODULE_REGISTRY: dict[str, ModuleSpec] = {}


def register(name: str, *, heavy: bool = False, needs_browser: bool = False, help: str = ""):
    def deco(fn):
        MODULE_REGISTRY[name] = ModuleSpec(name, heavy, needs_browser, help)
        return fn
    return deco
