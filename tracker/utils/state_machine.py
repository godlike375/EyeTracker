from dataclasses import dataclass
from typing import Callable, Any


@dataclass(slots=True)
class EventCheck:
    name: str
    happened: bool
    tip: str


class StateMachine:
    def __init__(self, events: list, on_state_changed: Callable[[str], None] = None):
        self._all_events = [EventCheck(name, happened, tip) for name, happened, tip in events]
        self._on_state_changed = on_state_changed
        self._last_tip = None

    def change_state(self, event_name: str, happened=True):
        for event in self._all_events:
            if event_name == event.name:
                event.happened = happened

        prioritized = self._get_most_prioritized_event()
        tip = prioritized.tip if prioritized else ''
        if tip != self._last_tip:
            self._last_tip = tip
            if self._on_state_changed:
                self._on_state_changed(tip)
        return tip

    def _get_most_prioritized_event(self):
        for event in self._all_events:
            if not event.happened:
                return event
        return None

    def reset(self):
        for event in self._all_events:
            event.happened = False

    @property
    def current_tip(self):
        return self._last_tip
