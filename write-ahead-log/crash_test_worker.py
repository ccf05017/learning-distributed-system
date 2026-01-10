"""크래시 테스트용 worker 스크립트

subprocess로 실행되어 특정 시점에 마커 파일을 생성하고 대기.
테스트에서 SIGKILL로 종료하여 크래시를 시뮬레이션한다.

사용법:
    python crash_test_worker.py <data_dir> <crash_point> <marker_file> <key> <value>

crash_point:
    - post_append: append 후, sync 전
    - post_flush: flush 후, fsync 전
    - post_sync: sync 완료 후, _apply_record 전
"""

import sys
import time
from pathlib import Path

from kv_store import KVStore


def create_marker_and_wait(marker_path: Path) -> None:
    """마커 파일 생성 후 무한 대기 (SIGKILL 대기)"""
    marker_path.touch()
    while True:
        time.sleep(1)


def main() -> None:
    if len(sys.argv) != 6:
        print(f"Usage: {sys.argv[0]} <data_dir> <crash_point> <marker_file> <key> <value>")
        sys.exit(1)

    data_dir = Path(sys.argv[1])
    crash_point = sys.argv[2]
    marker_file = Path(sys.argv[3])
    key = sys.argv[4]
    value = sys.argv[5]

    hooks = {
        "post_append_hook": None,
        "post_flush_hook": None,
        "post_sync_hook": None,
    }

    if crash_point == "post_append":
        hooks["post_append_hook"] = lambda: create_marker_and_wait(marker_file)
    elif crash_point == "post_flush":
        hooks["post_flush_hook"] = lambda: create_marker_and_wait(marker_file)
    elif crash_point == "post_sync":
        hooks["post_sync_hook"] = lambda: create_marker_and_wait(marker_file)
    else:
        print(f"Unknown crash point: {crash_point}")
        sys.exit(1)

    store = KVStore(data_dir=data_dir, **hooks)
    store.put(key, value)
    store.close()


if __name__ == "__main__":
    main()
