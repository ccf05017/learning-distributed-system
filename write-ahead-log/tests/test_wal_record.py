"""WAL 레코드 객체 테스트"""

import json

import pytest

from src.wal_record import ChecksumError, RecordType, WALRecord


class TestWALRecordBasic:
    """WALRecord 기본 구조 테스트"""

    def test_record_has_put_type(self):
        """PUT 타입 레코드를 생성할 수 있다"""
        record = WALRecord(RecordType.PUT, "key1", "value1")

        assert record.record_type == RecordType.PUT
        assert record.key == "key1"
        assert record.value == "value1"

    def test_record_has_del_type(self):
        """DEL 타입 레코드를 생성할 수 있다"""
        record = WALRecord(RecordType.DEL, "key1")

        assert record.record_type == RecordType.DEL
        assert record.key == "key1"
        assert record.value is None

    def test_serialize_put_record(self):
        """PUT 레코드를 바이트로 직렬화할 수 있다"""
        record = WALRecord(RecordType.PUT, "key1", "value1")
        data = record.serialize()

        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_deserialize_put_record(self):
        """바이트에서 PUT 레코드를 역직렬화할 수 있다"""
        original = WALRecord(RecordType.PUT, "key1", "value1")
        data = original.serialize()

        restored = WALRecord.deserialize(data)

        assert restored.record_type == original.record_type
        assert restored.key == original.key
        assert restored.value == original.value


class TestWALRecordChecksum:
    """레코드 무결성 테스트"""

    def test_serialized_record_includes_checksum(self):
        """직렬화된 레코드에 체크섬이 포함된다"""
        key, value = "key1", "value1"
        record = WALRecord(RecordType.PUT, key, value)

        payload = json.dumps({
            "type": RecordType.PUT.value,
            "key": key,
            "value": value,
        }).encode("utf-8")

        serialized = record.serialize()

        assert len(serialized) > len(payload)

    def test_corrupted_record_raises_error(self):
        """손상된 레코드 역직렬화 시 오류가 발생한다"""
        record = WALRecord(RecordType.PUT, "key1", "value1")
        data = bytearray(record.serialize())

        data[10] = (data[10] + 1) % 256

        with pytest.raises(ChecksumError):
            WALRecord.deserialize(bytes(data))


class TestWALRecordFraming:
    """레코드 프레이밍 테스트"""

    def test_serialized_record_ends_with_newline(self):
        """직렬화된 레코드는 줄바꿈으로 끝난다"""
        record = WALRecord(RecordType.PUT, "key1", "value1")
        data = record.serialize()

        assert data.endswith(b"\n")

    def test_multiple_records_can_be_split_by_newline(self):
        """여러 레코드를 줄바꿈으로 분리할 수 있다"""
        record1 = WALRecord(RecordType.PUT, "key1", "value1")
        record2 = WALRecord(RecordType.PUT, "key2", "value2")

        combined = record1.serialize() + record2.serialize()
        lines = combined.strip().split(b"\n")

        assert len(lines) == 2

        restored1 = WALRecord.deserialize(lines[0] + b"\n")
        restored2 = WALRecord.deserialize(lines[1] + b"\n")

        assert restored1.key == "key1"
        assert restored2.key == "key2"

    def test_value_with_newline_does_not_break_framing(self):
        """값에 줄바꿈이 포함되어도 프레이밍이 깨지지 않는다"""
        value_with_newline = "hello\nworld"
        record = WALRecord(RecordType.PUT, "key1", value_with_newline)

        data = record.serialize()
        lines = data.strip().split(b"\n")

        assert len(lines) == 1

        restored = WALRecord.deserialize(data)
        assert restored.value == value_with_newline
