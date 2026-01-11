"""WAL 레코드 객체"""

from enum import Enum


class RecordType(Enum):
    PUT = 1
    DEL = 2


class ChecksumError(Exception):
    pass


class WALRecord:
    def __init__(self, record_type: RecordType, key: str, value: str | None = None):
        pass

    def serialize(self) -> bytes:
        pass

    @classmethod
    def deserialize(cls, data: bytes) -> "WALRecord":
        pass
