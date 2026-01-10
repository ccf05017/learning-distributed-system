"""WAL 파일 관리 객체 테스트"""

from wal import WAL
from wal_record import RecordType, WALRecord


class TestWALContextManager:
    """WAL 컨텍스트 매니저 테스트"""

    def test_context_manager_closes_file(self, tmp_path):
        """with 블록 종료 시 파일이 닫힌다"""
        wal_path = tmp_path / "wal.log"

        with WAL(wal_path) as wal:
            wal.append(WALRecord(RecordType.PUT, "key1", "value1"))

        # with 블록 종료 후 파일에 데이터가 있어야 함
        assert wal_path.stat().st_size > 0


class TestWALWrite:
    """WAL 쓰기 테스트"""

    def test_append_record_to_file(self, tmp_path):
        """레코드를 파일에 append할 수 있다"""
        wal_path = tmp_path / "wal.log"
        wal = WAL(wal_path)

        record = WALRecord(RecordType.PUT, "key1", "value1")
        wal.append(record)
        wal.close()

        assert wal_path.exists()
        assert wal_path.stat().st_size > 0

    def test_append_returns_offset_before_write(self, tmp_path):
        """append()는 쓰기 전 파일 위치(offset)를 반환한다"""
        wal_path = tmp_path / "wal.log"
        wal = WAL(wal_path)

        # 첫 번째 append - offset은 0이어야 함
        offset1 = wal.append(WALRecord(RecordType.PUT, "key1", "value1"))
        assert offset1 == 0

        # 두 번째 append - offset은 첫 번째 레코드 크기만큼 증가
        offset2 = wal.append(WALRecord(RecordType.PUT, "key2", "value2"))
        assert offset2 > 0
        assert offset2 > offset1

        wal.close()

    def test_sync_flushes_to_disk(self, tmp_path):
        """sync 호출 시 디스크에 영구 저장된다"""
        wal_path = tmp_path / "wal.log"
        assert not wal_path.exists()

        wal = WAL(wal_path)

        record = WALRecord(RecordType.PUT, "key1", "value1")
        wal.append(record)
        wal.sync()

        content = wal_path.read_bytes()
        assert len(content) > 0


class TestWALRollback:
    """WAL 롤백 테스트"""

    def test_rollback_truncates_to_offset(self, tmp_path):
        """rollback(offset) 호출 시 해당 위치로 파일을 truncate한다"""
        wal_path = tmp_path / "wal.log"
        wal = WAL(wal_path)

        # 두 개의 레코드 작성
        offset1 = wal.append(WALRecord(RecordType.PUT, "key1", "value1"))
        offset2 = wal.append(WALRecord(RecordType.PUT, "key2", "value2"))
        wal.sync()

        # 두 번째 레코드 롤백
        wal.rollback(offset2)

        # 파일 크기가 offset2와 같아야 함
        assert wal_path.stat().st_size == offset2

        # 읽기로 확인 - 첫 번째 레코드만 남아있어야 함
        wal.close()
        records = list(WAL.read(wal_path))
        assert len(records) == 1
        assert records[0].key == "key1"

    def test_rollback_then_append_works(self, tmp_path):
        """rollback 후 다시 append하면 정상 동작한다"""
        wal_path = tmp_path / "wal.log"
        wal = WAL(wal_path)

        # 두 개의 레코드 작성
        wal.append(WALRecord(RecordType.PUT, "key1", "value1"))
        offset2 = wal.append(WALRecord(RecordType.PUT, "key2", "value2"))
        wal.sync()

        # 두 번째 레코드 롤백
        wal.rollback(offset2)

        # 새 레코드 추가
        wal.append(WALRecord(RecordType.PUT, "key3", "value3"))
        wal.close()

        # 읽기로 확인 - key1, key3만 있어야 함
        records = list(WAL.read(wal_path))
        assert len(records) == 2
        assert records[0].key == "key1"
        assert records[1].key == "key3"


class TestWALRead:
    """WAL 읽기 테스트"""

    def test_read_records_from_file(self, tmp_path):
        """파일에서 레코드를 순차적으로 읽을 수 있다"""
        wal_path = tmp_path / "wal.log"

        # 쓰기
        wal = WAL(wal_path)
        wal.append(WALRecord(RecordType.PUT, "key1", "value1"))
        wal.append(WALRecord(RecordType.PUT, "key2", "value2"))
        wal.close()

        # 읽기
        records = list(WAL.read(wal_path))

        assert len(records) == 2
        assert records[0].key == "key1"
        assert records[1].key == "key2"

    def test_read_skips_empty_lines(self, tmp_path):
        """빈 줄이 있어도 안전하게 건너뛴다"""
        wal_path = tmp_path / "wal.log"

        # 정상 레코드 작성
        wal = WAL(wal_path)
        wal.append(WALRecord(RecordType.PUT, "key1", "value1"))
        wal.close()

        # 빈 줄 추가 (불완전한 쓰기 시뮬레이션)
        with open(wal_path, "ab") as f:
            f.write(b"\n")
            f.write(b"\n")

        # 정상 레코드 추가
        wal = WAL(wal_path)
        wal.append(WALRecord(RecordType.PUT, "key2", "value2"))
        wal.close()

        # 읽기 - 빈 줄을 건너뛰고 모든 정상 레코드를 읽어야 함
        records = list(WAL.read(wal_path))

        assert len(records) == 2
        assert records[0].key == "key1"
        assert records[1].key == "key2"

    def test_read_stops_at_corrupted_record(self, tmp_path):
        """손상된 레코드를 만나면 그 직전까지만 읽는다"""
        wal_path = tmp_path / "wal.log"

        # 정상 레코드 2개 작성
        wal = WAL(wal_path)
        wal.append(WALRecord(RecordType.PUT, "key1", "value1"))
        wal.append(WALRecord(RecordType.PUT, "key2", "value2"))
        wal.close()

        # 손상된 레코드 추가
        with open(wal_path, "ab") as f:
            f.write(b"corrupted data\n")

        # 읽기 - 손상된 레코드 전까지만 읽어야 함
        records = list(WAL.read(wal_path))

        assert len(records) == 2
        assert records[0].key == "key1"
        assert records[1].key == "key2"


class TestWALCorruptionHandling:
    """Phase 8: WAL 손상/부분 레코드 처리"""

    def test_partial_record_at_end_is_ignored(self, tmp_path):
        """8.1 끝부분 불완전 레코드는 무시한다"""
        wal_path = tmp_path / "wal.log"

        # 정상 레코드 작성
        wal = WAL(wal_path)
        wal.append(WALRecord(RecordType.PUT, "key1", "value1"))
        wal.close()

        # 불완전 레코드 추가 (줄바꿈 없이 끊김)
        with open(wal_path, "ab") as f:
            f.write(b'{"type":"PUT","key":"key2"')  # 불완전한 JSON

        # 읽기 - 완전한 레코드만 반환
        records = list(WAL.read(wal_path))
        assert len(records) == 1
        assert records[0].key == "key1"

    def test_empty_wal_returns_no_records(self, tmp_path):
        """8.4 빈 WAL은 빈 상태로 복구한다"""
        wal_path = tmp_path / "wal.log"
        wal_path.touch()  # 빈 파일 생성

        records = list(WAL.read(wal_path))
        assert len(records) == 0

    def test_invalid_record_type_stops_reading(self, tmp_path):
        """8.3 잘못된 레코드 타입이면 읽기를 중단한다"""
        import json
        import zlib

        wal_path = tmp_path / "wal.log"

        # 정상 레코드 작성
        wal = WAL(wal_path)
        wal.append(WALRecord(RecordType.PUT, "key1", "value1"))
        wal.close()

        # 잘못된 타입의 레코드 추가 (유효한 체크섬이지만 잘못된 type 값)
        invalid_payload = json.dumps({"type": 999, "key": "key2", "value": "value2"}).encode()
        invalid_checksum = zlib.crc32(invalid_payload)
        with open(wal_path, "ab") as f:
            f.write(f"{invalid_checksum:08x} ".encode("ascii") + invalid_payload + b"\n")

        # 읽기 - 잘못된 레코드 전까지만 반환
        records = list(WAL.read(wal_path))
        assert len(records) == 1
        assert records[0].key == "key1"
