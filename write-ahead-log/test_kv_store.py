"""KV Store 기본 동작 테스트 (A 시나리오)"""

from unittest.mock import patch

import pytest

from kv_store import KVStore
from wal import WAL


class TestBasicOperations:
    """A. 기본 동작(정상 시나리오)"""

    def test_put_and_get_returns_value(self):
        """A1. PUT/GET 기본
        Given: 빈 스토어
        When: PUT(k, v1) 수행 후 GET(k)
        Then: GET(k)는 v1을 반환한다
        """
        store = KVStore()
        store.put("key1", "value1")

        assert store.get("key1") == "value1"

    def test_put_overwrites_existing_value(self):
        """A2. UPDATE(덮어쓰기)
        Given: PUT(k, v1)이 완료된 스토어
        When: PUT(k, v2) 수행 후 GET(k)
        Then: GET(k)는 v2를 반환한다
        """
        store = KVStore()
        store.put("key1", "value1")
        store.put("key1", "value2")

        assert store.get("key1") == "value2"

    def test_delete_removes_key(self):
        """A3. DELETE
        Given: PUT(k, v1)이 완료된 스토어
        When: DEL(k) 수행 후 GET(k)
        Then: GET(k)는 존재하지 않음을 반환한다
        """
        store = KVStore()
        store.put("key1", "value1")
        store.delete("key1")

        assert store.get("key1") is None

    def test_multiple_keys_are_independent(self):
        """A4. 다중 키 독립성
        Given: 빈 스토어
        When: PUT(k1, v1), PUT(k2, v2) 수행
        Then: GET(k1)=v1이고 GET(k2)=v2다
        """
        store = KVStore()
        store.put("key1", "value1")
        store.put("key2", "value2")

        assert store.get("key1") == "value1"
        assert store.get("key2") == "value2"


class TestWALWrite:
    """WAL 쓰기 테스트"""

    def test_put_creates_wal_file(self, tmp_path):
        """PUT 수행 시 WAL 파일에 레코드가 기록된다"""
        wal_path = tmp_path / "wal.log"
        assert not wal_path.exists()

        store = KVStore(data_dir=tmp_path)
        store.put("key1", "value1")

        assert wal_path.exists()
        assert wal_path.stat().st_size > 0

    def test_delete_writes_to_wal(self, tmp_path):
        """DEL 수행 시 WAL 파일에 레코드가 기록된다"""
        store = KVStore(data_dir=tmp_path)
        store.put("key1", "value1")

        wal_path = tmp_path / "wal.log"
        size_after_put = wal_path.stat().st_size

        store.delete("key1")

        assert wal_path.stat().st_size > size_after_put

    def test_close_flushes_and_closes_file(self, tmp_path):
        """정상 종료 시 버퍼가 flush되고 파일이 닫힌다"""
        key, value = "test_key", "test_value"

        store = KVStore(data_dir=tmp_path)
        store.put(key, value)
        store.close()

        # close 후 파일에 데이터가 있어야 함
        wal_path = tmp_path / "wal.log"
        content = wal_path.read_bytes()
        assert len(content) > 0


class TestWALRead:
    """WAL 읽기 테스트"""

    def test_recovers_put_from_wal(self, tmp_path):
        """WAL 파일에서 PUT 레코드를 읽어 상태를 복원한다"""
        key, value = "test_key", "test_value"

        store1 = KVStore(data_dir=tmp_path)
        store1.put(key, value)
        store1.close()

        store2 = KVStore(data_dir=tmp_path)
        assert store2.get(key) == value


class TestDurability:
    """B. 내구성/복구(정상 재시작)"""

    def test_data_persists_after_restart(self, tmp_path):
        """B1. 재시작 후 데이터 유지
        Given: PUT(k, v1)이 완료된 상태
        When: 프로세스를 정상 종료 후 재시작(Recovery 수행)
        Then: GET(k)는 v1을 반환한다
        """
        store = KVStore(data_dir=tmp_path)
        store.put("key1", "value1")
        store.close()

        store2 = KVStore(data_dir=tmp_path)
        assert store2.get("key1") == "value1"

    def test_last_value_persists_after_multiple_updates(self, tmp_path):
        """B2. 여러 업데이트 후 재시작
        Given: 동일 키에 여러 번 PUT 수행
        When: 정상 종료 후 재시작
        Then: GET(k)는 마지막 값을 반환한다
        """
        store = KVStore(data_dir=tmp_path)
        store.put("key1", "value1")
        store.put("key1", "value2")
        store.put("key1", "value3")
        store.close()

        store2 = KVStore(data_dir=tmp_path)
        assert store2.get("key1") == "value3"

    def test_delete_persists_after_restart(self, tmp_path):
        """B3. 삭제 후 재시작
        Given: PUT 후 DEL 수행
        When: 정상 종료 후 재시작
        Then: GET(k)는 None을 반환한다
        """
        store = KVStore(data_dir=tmp_path)
        store.put("key1", "value1")
        store.delete("key1")
        store.close()

        store2 = KVStore(data_dir=tmp_path)
        assert store2.get("key1") is None


class TestSyncFailureRollback:
    """7.3 sync 실패 시 자동 롤백"""

    def test_sync_failure_leaves_no_trace_in_wal(self, tmp_path):
        """sync 실패 시 WAL에 불완전 레코드가 남지 않는다"""
        store = KVStore(data_dir=tmp_path)
        store.put("key1", "value1")
        store.put("key2", "value2")

        # sync 실패 시뮬레이션
        with patch.object(store._wal, "sync", side_effect=IOError("Disk full")):
            with pytest.raises(IOError):
                store.put("key3", "value3")

        store.close()

        # WAL에는 key1, key2만 있어야 함
        wal_path = tmp_path / "wal.log"
        records = list(WAL.read(wal_path))
        assert len(records) == 2
        assert records[0].key == "key1"
        assert records[1].key == "key2"

    def test_sync_failure_no_recovery_after_restart(self, tmp_path):
        """sync 실패 후 재시작해도 실패한 연산은 복구되지 않는다"""
        store = KVStore(data_dir=tmp_path)
        store.put("key1", "value1")
        store.put("key2", "value2")

        # sync 실패 시뮬레이션
        with patch.object(store._wal, "sync", side_effect=IOError("Disk full")):
            with pytest.raises(IOError):
                store.put("key3", "value3")

        store.close()

        # 재시작 후 key3는 없어야 함
        store2 = KVStore(data_dir=tmp_path)
        assert store2.get("key1") == "value1"
        assert store2.get("key2") == "value2"
        assert store2.get("key3") is None
