from dataclasses import dataclass


@dataclass
class Toggle:
    dismissed_on_icon: float = float("-inf")

    def hidden(self, over_icon: bool, timestamp: float) -> None:
        self.dismissed_on_icon = timestamp if over_icon else float("-inf")

    def should_open(self, visible: bool, timestamp: float) -> bool:
        dismissed = 0 <= timestamp - self.dismissed_on_icon < 0.6
        self.dismissed_on_icon = float("-inf")
        return not visible and not dismissed
