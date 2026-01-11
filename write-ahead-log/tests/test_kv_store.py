"""KV Store 기본 동작 테스트 (A 시나리오)"""

from unittest.mock import patch

import pytest

from src.kv_store import KVStore
from src.wal import WAL


class TestBasicOperations:
    """A. 기본 동작(정상 시나리오)"""

    def test_put_and_get_returns_value(self, tmp_path):
        """A1. PUT/GET 기본
        Given: 빈 스토어
        When: PUT(k, v1) 수행 후 GET(k)
        Then: GET(k)는 v1을 반환한다
        """
        store = KVStore(tmp_path)
        store.put("key1", "value1")

        assert store.get("key1") == "value1"

    def test_put_overwrites_existing_value(self, tmp_path):
        """A2. UPDATE(덮어쓰기)
        Given: PUT(k, v1)이 완료된 스토어
        When: PUT(k, v2) 수행 후 GET(k)
        Then: GET(k)는 v2를 반환한다
        """
        store = KVStore(tmp_path)
        store.put("key1", "value1")
        store.put("key1", "value2")

        assert store.get("key1") == "value2"
#
    def test_delete_removes_key(self, tmp_path):
        """A3. DELETE
        Given: PUT(k, v1)이 완료된 스토어
        When: DEL(k) 수행 후 GET(k)
        Then: GET(k)는 존재하지 않음을 반환한다
        """
        store = KVStore(tmp_path)
        store.put("key1", "value1")
        store.delete("key1")

        assert store.get("key1") is None

    def test_multiple_keys_are_independent(self, tmp_path):
        """A4. 다중 키 독립성
        Given: 빈 스토어
        When: PUT(k1, v1), PUT(k2, v2) 수행
        Then: GET(k1)=v1이고 GET(k2)=v2다
        """
        store = KVStore(tmp_path)
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


class TestCheckpoint:
    """E. 체크포인트/로그 롤링"""

    def test_checkpoint_only_recovery(self, tmp_path):
        """E1. 체크포인트 후 재시작 - checkpoint만으로 복구
        Given: PUT 후 checkpoint 수행
        When: 재시작
        Then: checkpoint에서 상태 복구
        """
        store = KVStore(data_dir=tmp_path)
        store.put("key1", "value1")
        store.put("key2", "value2")
        store.checkpoint()

        # checkpoint 후 WAL이 비워졌는지 확인 (핵심!)
        wal_path = tmp_path / "wal.log"
        assert wal_path.stat().st_size == 0, "checkpoint 후 WAL은 비어야 함"

        # checkpoint 파일이 생성되었는지 확인
        checkpoint_path = tmp_path / "checkpoint.json"
        assert checkpoint_path.exists(), "checkpoint 파일이 없음"

        store.close()

        # 재시작 후 복구
        store2 = KVStore(data_dir=tmp_path)
        assert store2.get("key1") == "value1"
        assert store2.get("key2") == "value2"

    def test_checkpoint_plus_new_wal_recovery(self, tmp_path):
        """E2. 체크포인트 후 새 WAL - checkpoint + 새 WAL replay
        Given: checkpoint 후 새로운 PUT 수행
        When: 재시작
        Then: checkpoint + WAL 모두에서 복구
        """
        store = KVStore(data_dir=tmp_path)
        store.put("key1", "value1")
        store.put("key2", "value2")
        store.checkpoint()

        # 체크포인트 이후 새 데이터
        store.put("key3", "value3")
        store.put("key1", "updated1")  # 기존 키 업데이트
        store.close()

        # 재시작 후 복구 - checkpoint + WAL 모두 반영
        store2 = KVStore(data_dir=tmp_path)
        assert store2.get("key1") == "updated1"  # WAL에서 덮어씀
        assert store2.get("key2") == "value2"    # checkpoint에서
        assert store2.get("key3") == "value3"    # WAL에서

    def test_checkpoint_rename_failure_leaves_old_intact_and_cleans_tmp(self, tmp_path):
        """E3. checkpoint rename 실패 시 이전 checkpoint 유지 및 tmp 정리
        Given: 첫 번째 checkpoint 완료
        When: 두 번째 checkpoint 중 rename 실패
        Then: 이전 checkpoint.json 유지, tmp 파일 자체 정리됨
        """
        import os

        store = KVStore(data_dir=tmp_path)
        store.put("key1", "value1")
        store.checkpoint()

        checkpoint_path = tmp_path / "checkpoint.json"
        old_content = checkpoint_path.read_text()

        store.put("key2", "value2")

        # rename 실패 시뮬레이션
        with patch.object(os, "rename", side_effect=IOError("Rename failed")):
            with pytest.raises(IOError):
                store.checkpoint()

        # 이전 checkpoint가 손상되지 않았어야 함
        assert checkpoint_path.read_text() == old_content

        # tmp 파일은 자체 정리되어 없어야 함
        checkpoint_tmp = tmp_path / "checkpoint.tmp"
        assert not checkpoint_tmp.exists()

    def test_startup_cleans_orphaned_checkpoint_tmp(self, tmp_path):
        """E3b. 시작 시 고아 checkpoint.tmp 청소 (SIGKILL 시나리오)
        Given: SIGKILL로 인해 checkpoint.tmp가 남아있는 상태
        When: 재시작
        Then: checkpoint.tmp 삭제, checkpoint.json + WAL로 복구
        """
        store = KVStore(data_dir=tmp_path)
        store.put("key1", "value1")
        store.checkpoint()
        store.put("key2", "value2")
        store.close()

        # SIGKILL 시뮬레이션: checkpoint.tmp가 남아있음
        checkpoint_tmp = tmp_path / "checkpoint.tmp"
        checkpoint_tmp.write_text('{"key1": "corrupted", "key2": "corrupted"}')

        # 재시작 - tmp 파일 무시하고 정상 복구
        store2 = KVStore(data_dir=tmp_path)
        assert store2.get("key1") == "value1"
        assert store2.get("key2") == "value2"

        # tmp 파일이 청소됨
        assert not checkpoint_tmp.exists()

    def test_crash_after_checkpoint_rename_before_wal_truncate(self, tmp_path):
        """E4. checkpoint rename 직후 크래시 - WAL truncate 전
        Given: checkpoint.json rename 완료
        When: WAL rollback(truncate) 전 크래시
        Then: 재시작 시 checkpoint + WAL 중복 적용해도 정상 (idempotent)
        """
        store = KVStore(data_dir=tmp_path)
        store.put("key1", "value1")
        store.put("key2", "value2")

        # rollback을 무효화해서 WAL truncate 안 되게 함
        with patch.object(store._wal, "rollback"):
            store.checkpoint()

        # checkpoint 파일은 저장됨
        checkpoint_path = tmp_path / "checkpoint.json"
        assert checkpoint_path.exists()

        # WAL은 truncate 안 됨 (레코드 여전히 있음)
        wal_path = tmp_path / "wal.log"
        assert wal_path.stat().st_size > 0

        store.close()

        # 재시작 - checkpoint + WAL 모두 적용해도 정상
        store2 = KVStore(data_dir=tmp_path)
        assert store2.get("key1") == "value1"
        assert store2.get("key2") == "value2"

    def test_crash_after_wal_truncate_safe(self, tmp_path):
        """E5. WAL truncate 후 크래시 - checkpoint만으로 복구
        Given: checkpoint 완료, WAL truncate 완료
        When: 크래시 후 재시작
        Then: checkpoint만으로 정상 복구
        """
        store = KVStore(data_dir=tmp_path)
        store.put("key1", "value1")
        store.put("key2", "value2")
        store.checkpoint()

        # checkpoint 후 WAL은 비어있어야 함
        wal_path = tmp_path / "wal.log"
        assert wal_path.stat().st_size == 0

        store.close()

        # 재시작 - checkpoint만으로 복구
        store2 = KVStore(data_dir=tmp_path)
        assert store2.get("key1") == "value1"
        assert store2.get("key2") == "value2"


class TestReplayIdempotency:
    """F. 재적용 안전성 - Replay 멱등성"""

    def test_multiple_wal_replays_produce_same_state(self, tmp_path):
        """F1. 동일 WAL 여러 번 replay해도 동일한 최종 상태
        Given: WAL에 여러 연산이 기록됨
        When: WAL을 여러 번 replay
        Then: 매번 동일한 최종 상태
        """
        # WAL 생성
        store = KVStore(data_dir=tmp_path)
        store.put("key1", "value1")
        store.put("key2", "value2")
        store.put("key1", "updated1")
        store.delete("key2")
        store.put("key3", "value3")
        store.close()

        # 첫 번째 replay
        store1 = KVStore(data_dir=tmp_path)
        state1 = {
            "key1": store1.get("key1"),
            "key2": store1.get("key2"),
            "key3": store1.get("key3"),
        }
        store1.close()

        # 두 번째 replay
        store2 = KVStore(data_dir=tmp_path)
        state2 = {
            "key1": store2.get("key1"),
            "key2": store2.get("key2"),
            "key3": store2.get("key3"),
        }
        store2.close()

        # 세 번째 replay
        store3 = KVStore(data_dir=tmp_path)
        state3 = {
            "key1": store3.get("key1"),
            "key2": store3.get("key2"),
            "key3": store3.get("key3"),
        }

        # 모든 replay 결과가 동일해야 함
        assert state1 == state2 == state3
        assert state1 == {"key1": "updated1", "key2": None, "key3": "value3"}

    def test_duplicate_put_records_produce_correct_result(self, tmp_path):
        """F2. 중복 PUT 레코드도 올바른 결과
        Given: 동일 키에 대한 PUT이 여러 번 기록됨
        When: WAL replay
        Then: 마지막 값이 최종 상태
        """
        store = KVStore(data_dir=tmp_path)

        # 동일 키에 여러 번 PUT (실제로 이런 일이 발생할 수 있음)
        store.put("key1", "v1")
        store.put("key1", "v2")
        store.put("key1", "v3")
        store.put("key1", "v4")
        store.put("key1", "final")
        store.close()

        # replay
        store2 = KVStore(data_dir=tmp_path)
        assert store2.get("key1") == "final"

    def test_delete_then_put_same_key(self, tmp_path):
        """F2b. 삭제 후 다시 PUT해도 올바른 결과
        Given: PUT → DELETE → PUT 순서로 기록
        When: WAL replay
        Then: 마지막 PUT 값이 최종 상태
        """
        store = KVStore(data_dir=tmp_path)
        store.put("key1", "value1")
        store.delete("key1")
        store.put("key1", "resurrected")
        store.close()

        store2 = KVStore(data_dir=tmp_path)
        assert store2.get("key1") == "resurrected"


class TestBoundaryValues:
    """G1. 경계값 테스트 - 빈 키/긴 키/큰 값"""

    def test_empty_key_is_rejected_on_put(self, tmp_path):
        """빈 키는 PUT에서 거부된다"""
        store = KVStore(tmp_path)

        with pytest.raises(ValueError, match="key"):
            store.put("", "value")

    def test_empty_key_is_rejected_on_delete(self, tmp_path):
        """빈 키는 DELETE에서 거부된다"""
        store = KVStore(tmp_path)

        with pytest.raises(ValueError, match="key"):
            store.delete("")

    def test_long_key_works(self, tmp_path):
        """긴 키도 정상 동작한다"""
        store = KVStore(data_dir=tmp_path)
        long_key = "k" * 10000

        store.put(long_key, "value")
        assert store.get(long_key) == "value"

        store.close()

        # 재시작 후에도 복구
        store2 = KVStore(data_dir=tmp_path)
        assert store2.get(long_key) == "value"

    def test_large_value_works(self, tmp_path):
        """큰 값도 정상 동작한다"""
        store = KVStore(data_dir=tmp_path)
        large_value = "v" * 100000

        store.put("key", large_value)
        assert store.get("key") == large_value

        store.close()

        # 재시작 후에도 복구
        store2 = KVStore(data_dir=tmp_path)
        assert store2.get("key") == large_value

    def test_empty_value_works(self, tmp_path):
        """빈 값은 허용된다"""
        store = KVStore(tmp_path)

        store.put("key", "")
        assert store.get("key") == ""


class TestConcurrency:
    """G3. 동시성 - 멀티 스레드 안전성"""

    def test_concurrent_writes_do_not_corrupt_wal(self, tmp_path):
        """동시 쓰기가 WAL을 손상시키지 않는다"""
        import threading

        store = KVStore(data_dir=tmp_path)
        num_threads = 10
        writes_per_thread = 100
        errors = []

        def writer(thread_id):
            try:
                for i in range(writes_per_thread):
                    store.put(f"key_{thread_id}_{i}", f"value_{thread_id}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(num_threads)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 메모리 상태 확인 (close 전)
        memory_count = sum(
            1 for t in range(num_threads)
            for i in range(writes_per_thread)
            if store.get(f"key_{t}_{i}") == f"value_{t}_{i}"
        )

        store.close()

        # 에러 없이 완료
        assert not errors, f"Errors occurred: {errors}"

        # 메모리 상태는 정확해야 함
        assert memory_count == num_threads * writes_per_thread

        # 재시작 후 모든 데이터 복구 가능 (WAL 손상 없음)
        store2 = KVStore(data_dir=tmp_path)
        recovered_count = sum(
            1 for t in range(num_threads)
            for i in range(writes_per_thread)
            if store2.get(f"key_{t}_{i}") == f"value_{t}_{i}"
        )
        assert recovered_count == num_threads * writes_per_thread

    
    def test_concurrent_failed_put_does_not_lose_other_thread_commit(self, tmp_path):
        """한 스레드의 PUT 실패(rollback)가 다른 스레드의 커밋을 날리지 않아야 한다"""
        import threading

        store = KVStore(data_dir=tmp_path)

        a_appended = threading.Event()
        b_synced = threading.Event()
        a_error: list[Exception] = []
        b_error: list[Exception] = []

        original_append = store._wal.append
        original_sync = store._wal.sync

        def append_wrapped(record):
            offset = original_append(record)
            if record.key == "a":
                a_appended.set()
            return offset

        def sync_wrapped():
            if threading.current_thread().name == "writer-a":
                if not b_synced.wait(timeout=5):
                    raise TimeoutError("writer-b did not sync in time")
                raise OSError("injected fsync failure for writer-a")

            original_sync()
            b_synced.set()

        store._wal.append = append_wrapped
        store._wal.sync = sync_wrapped

        def writer_a():
            try:
                store.put("a", "va")
            except Exception as e:
                a_error.append(e)

        def writer_b():
            try:
                store.put("b", "vb")
            except Exception as e:
                b_error.append(e)

        ta = threading.Thread(target=writer_a, name="writer-a")
        tb = threading.Thread(target=writer_b, name="writer-b")

        ta.start()
        if not a_appended.wait(timeout=5):
            raise TimeoutError("writer-a did not append in time")
        tb.start()

        ta.join()
        tb.join()

        assert a_error, "writer-a should fail"
        assert not b_error, f"writer-b should succeed, got: {b_error}"
        assert store.get("b") == "vb"

        store.close()

        store2 = KVStore(data_dir=tmp_path)
        assert store2.get("b") == "vb"
