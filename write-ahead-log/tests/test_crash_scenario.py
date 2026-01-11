"""C. 장애 타이밍 주입 시나리오 테스트

Write Path 각 단계에서 크래시 시 동작 검증.
커밋 포인트는 fsync 완료 시점. 이전은 미커밋, 이후는 커밋됨.

테스트 방식:
- Mock 기반: 특정 시점 실패 시뮬레이션
- SIGKILL 기반: subprocess로 실제 프로세스 종료

SIGKILL 한계:
- 프로세스만 죽이고 OS는 계속 실행됨
- post_append: Python 버퍼 유실 → 테스트 가능
- post_flush: OS 커널 버퍼는 살아있음 → 전원 차단 시뮬레이션 불가
- post_sync: 디스크에 있음 → 테스트 가능
"""

# import os
# import signal
# import subprocess
# import sys
# import time
# from pathlib import Path
# from unittest.mock import patch

# import pytest

# from src.kv_store import KVStore


# # === Helper functions for SIGKILL-based tests ===


# def wait_for_marker(marker_path: Path, timeout: float = 5.0) -> bool:
#     """마커 파일이 생성될 때까지 대기"""
#     start = time.time()
#     while time.time() - start < timeout:
#         if marker_path.exists():
#             return True
#         time.sleep(0.01)
#     return False


# def spawn_and_kill(
#     data_dir: Path,
#     crash_point: str,
#     marker_file: Path,
#     operation: str,
#     key: str,
#     value: str | None = None,
# ) -> None:
#     """Worker 프로세스를 시작하고 마커 확인 후 SIGKILL"""
#     worker_script = Path(__file__).parent.parent / "src" / "crash_test_worker.py"
#     project_root = Path(__file__).parent.parent

#     args = [
#         sys.executable,
#         str(worker_script),
#         str(data_dir),
#         crash_point,
#         str(marker_file),
#         operation,
#         key,
#     ]
#     if value is not None:
#         args.append(value)

#     env = os.environ.copy()
#     env["PYTHONPATH"] = str(project_root) + os.pathsep + env.get("PYTHONPATH", "")

#     proc = subprocess.Popen(
#         args,
#         stdout=subprocess.PIPE,
#         stderr=subprocess.PIPE,
#         env=env,
#     )

#     try:
#         if not wait_for_marker(marker_file):
#             proc.kill()
#             stdout, stderr = proc.communicate()
#             raise TimeoutError(
#                 f"Marker file not created within timeout.\n"
#                 f"stdout: {stdout.decode()}\n"
#                 f"stderr: {stderr.decode()}"
#             )

#         os.kill(proc.pid, signal.SIGKILL)
#         proc.wait()
#     except Exception:
#         proc.kill()
#         raise


# # === C1: WAL append 이전 크래시 ===


# class TestC1AppendBeforeCrash:
#     """C1. WAL append 이전 크래시 → 데이터 없음"""

#     def test_crash_before_wal_append_loses_uncommitted_data(self, tmp_path):
#         """C1. WAL append 이전 크래시
#         Given: 두 개의 PUT이 완료된 상태
#         When: 세 번째 PUT 중 WAL append 전에 크래시 발생
#         Then: 재시작 후 처음 두 개만 존재하고 세 번째는 없다
#         """
#         store = KVStore(data_dir=tmp_path)
#         store.put("key1", "value1")
#         store.put("key2", "value2")

#         with patch.object(store._wal, "append", side_effect=Exception("Crash!")):
#             try:
#                 store.put("key3", "value3")
#             except Exception:
#                 pass

#         store.close()

#         store2 = KVStore(data_dir=tmp_path)
#         assert store2.get("key1") == "value1"
#         assert store2.get("key2") == "value2"
#         assert store2.get("key3") is None


# # === C2: WAL append 후 fsync 전 크래시 ===


# class TestC2AppendAfterSyncBefore:
#     """C2. WAL append 후 fsync 전 크래시 → 미커밋 상태"""

#     def test_sync_failure_raises_exception_and_skips_memtable(self, tmp_path):
#         """C2-mock. sync 실패 시 예외 발생, 메모리 미반영
#         커밋 포인트는 fsync 완료 시점. sync 실패 = 미커밋 = 연산 실패.
#         """
#         store = KVStore(data_dir=tmp_path)
#         store.put("key1", "value1")
#         store.put("key2", "value2")

#         with patch.object(store._wal, "sync", side_effect=IOError("Disk full")):
#             with pytest.raises(IOError):
#                 store.put("key3", "value3")

#         assert store.get("key1") == "value1"
#         assert store.get("key2") == "value2"
#         assert store.get("key3") is None

#     def test_crash_after_append_before_sync_no_recovery(self, tmp_path):
#         """C2-sigkill. append 후 sync 전 크래시 → Python 버퍼 유실"""
#         marker_file = tmp_path / "marker"

#         store = KVStore(data_dir=tmp_path)
#         store.put("key1", "value1")
#         store.put("key2", "value2")
#         store.close()

#         spawn_and_kill(tmp_path, "post_append", marker_file, "put", "key3", "value3")

#         store2 = KVStore(data_dir=tmp_path)
#         assert store2.get("key1") == "value1"
#         assert store2.get("key2") == "value2"
#         assert store2.get("key3") is None

#     def test_crash_after_flush_before_fsync_uncertain(self, tmp_path):
#         """C2-sigkill. flush 후 fsync 전 크래시 → 불확정 상태
#         SIGKILL은 OS를 죽이지 않으므로 OS가 버퍼를 flush할 수 있음.
#         이 테스트는 SIGKILL 한계와 불확정 상태를 문서화.
#         """
#         marker_file = tmp_path / "marker"

#         store = KVStore(data_dir=tmp_path)
#         store.put("key1", "value1")
#         store.put("key2", "value2")
#         store.close()

#         spawn_and_kill(tmp_path, "post_flush", marker_file, "put", "key3", "value3")

#         store2 = KVStore(data_dir=tmp_path)
#         assert store2.get("key1") == "value1"
#         assert store2.get("key2") == "value2"
#         # key3는 있을 수도 없을 수도 있음 - OS/파일시스템에 의존
#         key3_result = store2.get("key3")
#         print(f"post_flush crash: key3 = {key3_result}")


# # === C3: WAL fsync 후 크래시 ===


# class TestC3SyncAfterCrash:
#     """C3. WAL fsync 후 크래시 → WAL replay로 복구"""

#     def test_crash_after_sync_before_memtable_recovers(self, tmp_path):
#         """C3. fsync 후 MemTable 적용 전 크래시 → WAL replay로 복구
#         sync 완료 = 커밋됨. 메모리 적용 전 크래시여도 WAL에서 복구.
#         """
#         marker_file = tmp_path / "marker"

#         store = KVStore(data_dir=tmp_path)
#         store.put("key1", "value1")
#         store.put("key2", "value2")
#         store.close()

#         spawn_and_kill(tmp_path, "post_sync", marker_file, "put", "key3", "value3")

#         store2 = KVStore(data_dir=tmp_path)
#         assert store2.get("key1") == "value1"
#         assert store2.get("key2") == "value2"
#         assert store2.get("key3") == "value3"


# # === C6: DEL 장애 타이밍 ===


# class TestC6DeleteCrash:
#     """C6. DEL 장애 타이밍 → PUT과 동일 패턴 적용"""

#     def test_delete_crash_before_append_keeps_data(self, tmp_path):
#         """C6. DEL append 이전 크래시 → 삭제 안 됨 (데이터 유지)
#         Given: key1이 존재하는 상태
#         When: DEL 중 append 전에 크래시
#         Then: 재시작 후 key1 여전히 존재
#         """
#         store = KVStore(data_dir=tmp_path)
#         store.put("key1", "value1")

#         with patch.object(store._wal, "append", side_effect=Exception("Crash!")):
#             try:
#                 store.delete("key1")
#             except Exception:
#                 pass

#         store.close()

#         store2 = KVStore(data_dir=tmp_path)
#         assert store2.get("key1") == "value1"  # 삭제 안 됨

#     def test_delete_crash_after_sync_removes_data(self, tmp_path):
#         """C6. DEL fsync 후 크래시 → 삭제 상태 복구
#         Given: key1이 존재하는 상태
#         When: DEL 중 sync 완료 후 크래시
#         Then: 재시작 후 key1 없음 (삭제됨)
#         """
#         marker_file = tmp_path / "marker"

#         store = KVStore(data_dir=tmp_path)
#         store.put("key1", "value1")
#         store.close()

#         spawn_and_kill(tmp_path, "post_sync", marker_file, "delete", "key1")

#         store2 = KVStore(data_dir=tmp_path)
#         assert store2.get("key1") is None  # 삭제됨
