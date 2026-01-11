"""WAL 레코드 객체"""

import hashlib
import json

from enum import Enum


class RecordType(Enum):
    PUT = 1
    DEL = 2


class ChecksumError(Exception):
    pass


def _compute_checksum(record_type: int, key: str, value: str | None) -> str:
        content = f"{record_type}:{key}:{value}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class WALRecord:
    def __init__(self, record_type: RecordType, key: str, value: str | None = None):
        self.record_type = record_type
        self.key = key
        self.value = value

    def serialize(self) -> bytes:
        checksum = _compute_checksum(self.record_type.value, self.key, self.value)

        data = {
            "checksum": checksum,
            "record_type": self.record_type.value,
            "key": self.key,
            "value": self.value
        }

        return json.dumps(data).encode("utf-8") + b"\n"

    @classmethod
    def deserialize(cls, data: bytes) -> "WALRecord":
        json_data = json.loads(data.decode("utf-8"))

        computed_checksum = _compute_checksum(json_data["record_type"], json_data["key"], json_data["value"])
        if computed_checksum != json_data["checksum"]:
             raise ChecksumError()

        return WALRecord(
            RecordType(json_data["record_type"]),
            json_data["key"],
            json_data["value"]
        )
    
