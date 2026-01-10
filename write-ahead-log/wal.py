"""WAL 파일 관리 객체"""

import os
from collections.abc import Iterator
from pathlib import Path

from wal_record import ChecksumError, WALRecord


class WAL:
    def __init__(self, path: Path):
        self._path = path
        self._file = open(path, "ab")

    def __enter__(self) -> "WAL":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def append(self, record: WALRecord) -> None:
        self._file.write(record.serialize())

    def sync(self) -> None:
        self._file.flush()
        os.fsync(self._file.fileno())

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
