"""WAL 기반 KV Store"""

from collections.abc import Callable
from pathlib import Path


class KVStore:
    def __init__(
        self,
        data_dir: Path | None = None,
        post_append_hook: Callable[[], None] | None = None,
        post_flush_hook: Callable[[], None] | None = None,
        post_sync_hook: Callable[[], None] | None = None,
    ):
        pass

    def put(self, key: str, value: str) -> None:
        pass

    def get(self, key: str) -> str | None:
        pass

    def delete(self, key: str) -> None:
        pass

    def checkpoint(self) -> None:
        pass

    def close(self) -> None:
        pass
