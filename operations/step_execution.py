from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class StepExecution:
    run_login: Callable[[], None]
    run_change_warehouse: Callable[[], None]
    run_post_message: Callable[[str | None], bool]
    run_receive: Callable[..., bool]
    run_loading: Callable[..., bool]
    run_open_ui: Callable[..., bool]
