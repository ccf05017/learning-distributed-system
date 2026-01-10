"""WAL 기반 KV Store"""

from pathlib import Path


class KVStore:
    def __init__(self, data_dir: Path | None = None):
        self._data = {}
        self._wal_file = None

        if data_dir:
            wal_path = data_dir / "wal.log"
            if wal_path.exists():
                self._recover(wal_path)
            self._wal_file = open(wal_path, "a")

    def _recover(self, wal_path: Path) -> None:
        with open(wal_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                op = parts[0]
                if op == "PUT":
                    self._data[parts[1]] = parts[2]
                elif op == "DEL":
                    if parts[1] in self._data:
                        del self._data[parts[1]]

    def put(self, key: str, value: str) -> None:
        if self._wal_file:
            self._wal_file.write(f"PUT\t{key}\t{value}\n")
            self._wal_file.flush()
        self._data[key] = value

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def delete(self, key: str) -> None:
        if self._wal_file:
            self._wal_file.write(f"DEL\t{key}\n")
            self._wal_file.flush()
        if key in self._data:
            del self._data[key]

    def close(self) -> None:
        if self._wal_file:
            self._wal_file.flush()
            self._wal_file.close()
