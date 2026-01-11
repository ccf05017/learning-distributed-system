"""WAL 기반 KV Store"""

import json
import os
import threading
from collections.abc import Callable
from pathlib import Path

from src.wal import WAL
from src.wal_record import RecordType, WALRecord


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
        self._data_dir = data_dir
        self._lock = threading.Lock()

        if data_dir:
            checkpoint_path = data_dir / "checkpoint.json"
            checkpoint_tmp = data_dir / "checkpoint.tmp"
            wal_path = data_dir / "wal.log"

            # 이전 실행의 고아 tmp 파일 청소 (SIGKILL 등)
            if checkpoint_tmp.exists():
                checkpoint_tmp.unlink()

            # 체크포인트에서 복구
            if checkpoint_path.exists():
                with open(checkpoint_path) as f:
                    self._data = json.load(f)

            # WAL replay (체크포인트 이후 기록)
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
        if not key:
            raise ValueError("key cannot be empty")
        with self._lock:
            record = WALRecord(RecordType.PUT, key, value)
            if self._wal:
                offset = self._wal.append(record)
                try:
                    self._wal.sync()
                except Exception:
                    self._wal.rollback(offset)
                    raise
            self._apply_record(record)

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def delete(self, key: str) -> None:
        if not key:
            raise ValueError("key cannot be empty")
        with self._lock:
            record = WALRecord(RecordType.DEL, key)
            if self._wal:
                offset = self._wal.append(record)
                try:
                    self._wal.sync()
                except Exception:
                    self._wal.rollback(offset)
                    raise
            self._apply_record(record)

    def checkpoint(self) -> None:
        """현재 상태를 체크포인트로 저장하고 WAL을 초기화"""
        if not self._data_dir:
            return

        with self._lock:
            # WAL을 먼저 sync하여 모든 데이터가 디스크에 있도록 함
            if self._wal:
                self._wal.sync()

            checkpoint_path = self._data_dir / "checkpoint.json"
            checkpoint_tmp = self._data_dir / "checkpoint.tmp"

            # tmp 파일에 먼저 작성
            with open(checkpoint_tmp, "w") as f:
                json.dump(self._data, f)
                f.flush()
                os.fsync(f.fileno())

            # atomic rename (POSIX)
            try:
                os.rename(checkpoint_tmp, checkpoint_path)
            except Exception:
                # 실패 시 tmp 파일 정리
                checkpoint_tmp.unlink(missing_ok=True)
                raise

            # WAL 초기화 (체크포인트에 모든 상태가 있으므로)
            if self._wal:
                self._wal.rollback(0)

    def close(self) -> None:
        with self._lock:
            if self._wal:
                self._wal.close()
