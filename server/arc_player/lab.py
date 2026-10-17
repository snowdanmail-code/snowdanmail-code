"""Independent playable test transport. NOT an interface to external applications."""
from __future__ import annotations
from .core import Action, VerifiedCommand

class ControlledPlayChipExecutor:
    def __init__(self):
        self.history: list[VerifiedCommand] = []
        self._last = set()

    def execute(self, command: VerifiedCommand) -> bool:
        if (command.hand_id, command.revision) in self._last:
            return False
        if command.action is Action.WAIT:
            return False
        self._last.add((command.hand_id, command.revision))
        self.history.append(command)
        return True
