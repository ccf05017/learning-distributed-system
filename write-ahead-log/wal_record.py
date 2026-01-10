"""WAL 레코드 객체"""

import json
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
        # 줄 기반 파싱을 위해 레코드 전체를 텍스트 안전한 바이트로 구성한다.
        # 형식: "{crc32_hex} {json_payload}\n"
        header = f"{checksum:08x} ".encode("ascii")
        return header + payload + b"\n"

    @classmethod
    def deserialize(cls, data: bytes) -> "WALRecord":
        data = data.rstrip(b"\n")
        try:
            checksum_hex, payload = data.split(b" ", 1)
            stored_checksum = int(checksum_hex.decode("ascii"), 16)
        except Exception as e:
            raise ChecksumError("Invalid checksum header") from e

        computed_checksum = zlib.crc32(payload)
        if stored_checksum != computed_checksum:
            raise ChecksumError("Checksum mismatch")

        parsed = json.loads(payload.decode("utf-8"))
        return cls(
            RecordType(parsed["type"]),
            parsed["key"],
            parsed["value"],
        )
