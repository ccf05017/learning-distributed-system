"""WAL 기반 KV Store"""

from collections.abc import Callable
from pathlib import Path

from wal import WAL
from wal_record import RecordType, WALRecord


class KVStore:
    def __init__(
        self,
        data_dir: Path | None = None,
        post_append_hook: Callable[[], None] | None = None,
        post_flush_hook: Callable[[], None] | None = None,
        post_sync_hook: Callable[[], None] | None = None,
    ):
        self._data = {}
        self._wal = None

        if data_dir:
            wal_path = data_dir / "wal.log"
            if wal_path.exists():
                self._recover(wal_path)
            self._wal = WAL(
                wal_path,
                post_append_hook=post_append_hook,
                post_flush_hook=post_flush_hook,
                post_sync_hook=post_sync_hook,
            )

    def _apply_record(self, record: WALRecord) -> None:
        if record.record_type == RecordType.PUT:
            self._data[record.key] = record.value
        elif record.record_type == RecordType.DEL:
            if record.key in self._data:
                del self._data[record.key]

    def _recover(self, wal_path: Path) -> None:
        for record in WAL.read(wal_path):
            self._apply_record(record)

    def put(self, key: str, value: str) -> None:
        record = WALRecord(RecordType.PUT, key, value)
        if self._wal:
            self._wal.append(record)
            self._wal.sync()
        self._apply_record(record)

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def delete(self, key: str) -> None:
        record = WALRecord(RecordType.DEL, key)
        if self._wal:
            self._wal.append(record)
            self._wal.sync()
        self._apply_record(record)

    def close(self) -> None:
        if self._wal:
            self._wal.close()
