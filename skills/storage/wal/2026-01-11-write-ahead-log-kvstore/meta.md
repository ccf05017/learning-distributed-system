# 2계층 산출물 템플릿

## 문서 메타
- 제목: WAL 기반 단일 노드 KVStore 구현/검증 회고 (TDD + 크래시/손상 시나리오)
- 작성일: 2026-01-11
- 주제/범위: 단일 노드 KVStore에서 WAL을 “fsync=commit(ack)” 규약으로 구현하고, 재시작/손상/체크포인트/롤링을 테스트로 잠근 과정
- 선행지식(필수/권장):
  - 필수: 파일 I/O, flush vs fsync 의미, 기본 단위테스트(pytest)
  - 권장: replay(재적용) 멱등성, 체크포인트(write-tmp-then-rename) 패턴
- 목표 역량(예: 테스트 설계, 디버깅, 성능 추론, 분산시스템 패턴 적용 등): 시나리오 기반 테스트 설계, 내구성/크래시 모델링, 로그 프레이밍/체크섬 사고, 반례 기반 디버깅
- 최종 산출물(코드/문서/실험/데모 링크):
  - 구현: `write-ahead-log/src/kv_store.py`, `write-ahead-log/src/wal.py`, `write-ahead-log/src/wal_record.py`
  - 테스트: `write-ahead-log/tests/test_kv_store.py`, `write-ahead-log/tests/test_wal.py`, `write-ahead-log/tests/test_wal_record.py`, `write-ahead-log/tests/test_crash_scenario.py`
  - 문서: `write-ahead-log/plan.md`, `write-ahead-log/test-guide.md`, `write-ahead-log/docs/crash-test-limitations.md`, `write-ahead-log/docs/debugging-lesson-checksum-newline.md`
  - 데모: `write-ahead-log/scripts/demo_concurrent_rollback_truncation.py`
- 난이도(1~5): 3
- 난이도 규약(이 문서에서 사용하는 기준):
  - 1: 개념 1~2개 + 기본 기능 테스트 중심
  - 2: 파일 I/O/포맷이 섞이지만 크래시/동시성은 거의 없음
  - 3: 내구성/복구(replay) + 손상/부분레코드 등 실패모드 포함
  - 4: 계약/의미론(예: `fsync` 실패 의미) 설계가 핵심(테스트/구현 전체에 영향)
  - 5: 분산/합의/복제/정확히 한 번 의미론 등 검증 난이도 높음
- 태그: #storage #wal #durability #fsync #checkpoint #replay #crash-testing #pytest

## 관련 문서
- Layer 0: `skills/storage/wal/2026-01-11-write-ahead-log-kvstore/layer_0.md`
- Layer 1: `skills/storage/wal/2026-01-11-write-ahead-log-kvstore/layer_1.md`
