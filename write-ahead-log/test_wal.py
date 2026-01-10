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
