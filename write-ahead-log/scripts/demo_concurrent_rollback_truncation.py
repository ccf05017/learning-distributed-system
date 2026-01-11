"""동시성 버그 데모: 한 스레드의 rollback(truncate)이 다른 스레드의 커밋을 날릴 수 있음.

실행:
  .venv/bin/python write-ahead-log/scripts/demo_concurrent_rollback_truncation.py
"""

import tempfile
import threading
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.kv_store import KVStore


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        store = KVStore(data_dir=data_dir)

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
                b_synced.wait(timeout=5)
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
        a_appended.wait(timeout=5)
        tb.start()

        ta.join()
        tb.join()

        print(f"in-memory: a={store.get('a')!r} b={store.get('b')!r}")
        print(f"errors: writer-a={a_error!r} writer-b={b_error!r}")

        store.close()

        store2 = KVStore(data_dir=data_dir)
        print(f"after restart: a={store2.get('a')!r} b={store2.get('b')!r}")


if __name__ == "__main__":
    main()
