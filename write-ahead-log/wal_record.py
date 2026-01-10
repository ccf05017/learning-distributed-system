"""WAL 레코드 객체"""

import json
import struct
import zlib
from enum import Enum


class RecordType(Enum):
    PUT = 1
    DEL = 2


class ChecksumError(Exception):
    pass


class WALRecord:
    def __init__(self, record_type: RecordType, key: str, value: str | None = None):
        self.record_type = record_type
        self.key = key
        self.value = value

    def serialize(self) -> bytes:
        data = {
            "type": self.record_type.value,
            "key": self.key,
            "value": self.value,
        }
        payload = json.dumps(data).encode("utf-8")
        checksum = zlib.crc32(payload)
        return struct.pack(">I", checksum) + payload + b"\n"

    @classmethod
    def deserialize(cls, data: bytes) -> "WALRecord":
        data = data.rstrip(b"\n")
        stored_checksum = struct.unpack(">I", data[:4])[0]
        payload = data[4:]

        computed_checksum = zlib.crc32(payload)
        if stored_checksum != computed_checksum:
            raise ChecksumError("Checksum mismatch")

        parsed = json.loads(payload.decode("utf-8"))
        return cls(
            RecordType(parsed["type"]),
            parsed["key"],
            parsed["value"],
        )
