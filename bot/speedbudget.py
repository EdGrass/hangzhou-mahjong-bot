# -*- coding: utf-8 -*-
"""Draw-decision BUDGET variants: bound the discard computation so the client returns to
the event stream sooner and stops missing ~22% of claim windows (R1064, engineering).

`SpeedC151._pick_discard` already supports `budget_ms` (falls back to the fast
`_best_discard_t` when the deadline passes) -- these subclasses just expose it on the
current candidates.  Trade-off to measure: how many draw decisions change (quality cost)
vs how much latency drops (window capture gain).
"""
from __future__ import annotations

from .speedc151 import SpeedC151
from .speedvaluemeldmore0chi import SpeedValueMeldMore0Chi
from .speedvalue import SpeedValue


class _BudgetMixin:
    budget_ms = 200.0

    def __init__(self, name=None, budget_ms=None):
        # NOTE: SpeedValue/SpeedC151.__init__ defaults budget_ms to None and would
        # overwrite the class attribute, so capture the desired value first and set it
        # only after the chain has finished.
        want = float(budget_ms) if budget_ms is not None else float(self.budget_ms)
        if name is None:
            name = getattr(self, "DEFAULT_NAME", self.__class__.__name__.lower())
        super().__init__(name)
        self.budget_ms = want


class SpeedValueBudget(_BudgetMixin, SpeedValue):
    """`speedvalue` with a bounded draw-decision budget (default 200 ms)."""

    DEFAULT_NAME = "speedvaluebudget"

    def __init__(self, name=None, budget_ms=None):
        super().__init__(name, budget_ms)


class SpeedMeldMore0ChiBudget(_BudgetMixin, SpeedValueMeldMore0Chi):
    """`SpeedValueMeldMore0Chi` with a bounded draw-decision budget."""

    DEFAULT_NAME = "speedmeldmore0chibudget"

    def __init__(self, name=None, budget_ms=None):
        super().__init__(name, budget_ms)


class SpeedC151Budget(_BudgetMixin, SpeedC151):
    """`speedc151` with a bounded draw-decision budget (baseline probe)."""

    DEFAULT_NAME = "speedc151budget"

    def __init__(self, name=None, budget_ms=None):
        super().__init__(name, budget_ms)
