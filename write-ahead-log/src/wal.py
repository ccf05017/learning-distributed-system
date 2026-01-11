"""WAL 파일 관리 객체"""

from collections.abc import Callable, Iterator
from pathlib import Path

from src.wal_record import WALRecord


class WAL:
    def __init__(
        self,
        path: Path,
        post_append_hook: Callable[[], None] | None = None,
        post_flush_hook: Callable[[], None] | None = None,
        post_sync_hook: Callable[[], None] | None = None,
    ):
        pass

    def __enter__(self) -> "WAL":
        pass

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def append(self, record: WALRecord) -> int:
        pass

    def sync(self) -> None:
        pass

    def rollback(self, offset: int) -> None:
        pass

    def close(self) -> None:
        pass

    @classmethod
    def read(cls, path: Path) -> Iterator[WALRecord]:
        pass
