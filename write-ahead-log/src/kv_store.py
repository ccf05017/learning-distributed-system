"""WAL 기반 KV Store"""

import json
import os
import threading

from collections.abc import Callable
from pathlib import Path
from src.wal import WAL
from src.wal_record import WALRecord, RecordType

class KVStore:
    def __init__(
        self,
        data_dir: Path | None = None,
        post_append_hook: Callable[[], None] | None = None,
        post_flush_hook: Callable[[], None] | None = None,
        post_sync_hook: Callable[[], None] | None = None,
    ):
        self._store_data = {}
        self._lock = threading.Lock()

        if data_dir:
            self._wal_path = data_dir / "wal.log"
            self._checkpoint_tmp_path = data_dir / "checkpoint.tmp"
            self._checkpoint_path = data_dir / "checkpoint.json"

            if self._checkpoint_tmp_path.exists:
                self._checkpoint_tmp_path.unlink(missing_ok=True)

            if self._wal_path.exists():
                # 체크포인트 활용 복구
                if self._checkpoint_path.exists():
                    with open(self._checkpoint_path, "r") as f:
                        self._store_data = json.load(f)

                # 체크포인트에 없는 변경사항이 있는 경우 복구
                for record in WAL.read(self._wal_path):
                    if record.record_type == RecordType.PUT:
                        self._store_data[record.key] = record.value
                    if record.record_type == RecordType.DEL:
                        self._store_data.pop(record.key)

            self._wal = WAL(self._wal_path)
        else:
            raise Exception("data_dir is needed")

    # 매번 sync 하기 때문에 비효율적이긴 함 (학습 차원 허용. 실제로는 bulk나 다른 방안 고려 필요함)
    def put(self, key: str, value: str) -> None:
        with self._lock:
            if not key:
                raise ValueError("key cannot be empty")

            try:
                offset = self._wal.append(WALRecord(RecordType.PUT, key, value))
                self._wal.sync()
            except Exception:
                self._wal.rollback(offset)
                raise

            self._store_data[key] = value

    def get(self, key: str) -> str | None:
        return self._store_data.get(key, None)

    # 매번 sync 하기 때문에 비효율적이긴 함 (학습 차원 허용. 실제로는 bulk나 다른 방안 고려 필요함)
    def delete(self, key: str) -> None:
        with self._lock:
            if not key:
                raise ValueError("key cannot be empty")

            self._wal.append(WALRecord(RecordType.DEL, key))
            self._wal.sync()
            self._store_data.pop(key, None)

    # 체크포인트가 없어도 복구 자체는 가능함
    # 하지만 이런 정리 작업이 없으면 로그 데이터가 무한정 늘어나기 때문에 효율을 위한 스냅샷을 남김
    # 이 외에도 분산 처리하건 오래된 로그를 날리건 다른 방법은 얼마든지 존재함. 추가로 고민할 거리
    def checkpoint(self) -> None:
        with self._lock:
            with open(self._checkpoint_tmp_path, "w") as f:
                f.write(json.dumps(self._store_data))
                f.flush
                os.fsync(f.fileno())
            
            try:
                # 굳이 왜 rename을 하드라..?
                # 원자성 때문이었나..? 파일 쓰던 도중에 죽으면 안되니까..?
                # 쓰던 중에는 무조건 tmp고 완전히 적힌 파일만 체크포인트로 취급하기 위해서였나..?
                os.rename(self._checkpoint_tmp_path,  self._checkpoint_path)
            except Exception:
                self._checkpoint_tmp_path.unlink(missing_ok=True)
                raise

            if self._wal:
                self._wal.rollback(0)

    def close(self) -> None:
        with self._lock:
            self._wal.close()
