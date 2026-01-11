"""WAL 파일 관리 객체"""
import os
import json

from collections.abc import Callable, Iterator
from pathlib import Path

from src.wal_record import WALRecord, ChecksumError


class WAL:
    def __init__(
        self,
        path: Path,
        post_append_hook: Callable[[], None] | None = None,
        post_flush_hook: Callable[[], None] | None = None,
        post_sync_hook: Callable[[], None] | None = None,
    ):
        self._path = path
        self._file = open(self._path, "ab")

    def __enter__(self) -> "WAL":
        pass

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    def append(self, record: WALRecord) -> int:
        offset = self._file.tell()
        self._file.write(record.serialize())
        return offset

    def sync(self) -> None:
        self._file.flush()
        os.fsync(self._file.fileno())

    def rollback(self, offset: int) -> None:
        self._file.flush()
        self._file.truncate(offset)
        self._file.seek(offset)

    def close(self) -> None:
        self._file.flush()
        self._file.close()

    # WAL 읽기는 초기 단계에서만 실행되고, 읽기와 쓰기는 동시에 수행 불가능하기 때문에 
    @classmethod
    def read(cls, path: Path) -> Iterator[WALRecord]:
        path = Path(path)

        if not path.exists:
            return
        
        with open(path, "rb") as f:
            for line in f:
                striped = line.strip()
                
                if not striped:
                    continue
                try:
                    yield WALRecord.deserialize(line)
                except (json.JSONDecodeError, ChecksumError, KeyError, ValueError):
                    # 손상된 레코드 발견 시 중단
                    return
