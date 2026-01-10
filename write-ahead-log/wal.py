"""WAL 파일 관리 객체"""

import os
from collections.abc import Callable, Iterator
from pathlib import Path

from wal_record import ChecksumError, WALRecord


class WAL:
    def __init__(
        self,
        path: Path,
        post_append_hook: Callable[[], None] | None = None,
        post_flush_hook: Callable[[], None] | None = None,
        post_sync_hook: Callable[[], None] | None = None,
    ):
        self._path = path
        self._file = open(path, "ab")
        self._post_append_hook = post_append_hook
        self._post_flush_hook = post_flush_hook
        self._post_sync_hook = post_sync_hook

    def __enter__(self) -> "WAL":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def append(self, record: WALRecord) -> None:
        self._file.write(record.serialize())
        if self._post_append_hook:
            self._post_append_hook()

    def sync(self) -> None:
        self._file.flush()
        if self._post_flush_hook:
            self._post_flush_hook()
        os.fsync(self._file.fileno())
        if self._post_sync_hook:
            self._post_sync_hook()

    def close(self) -> None:
        self.sync()
        self._file.close()

    @classmethod
    def read(cls, path: Path) -> Iterator[WALRecord]:
        with open(path, "rb") as f:
            for line in f:
                if line.strip():
                    try:
                        yield WALRecord.deserialize(line)
                    except ChecksumError:
                        return
