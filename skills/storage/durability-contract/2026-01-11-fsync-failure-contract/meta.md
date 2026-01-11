# 2계층 산출물 템플릿

## 문서 메타
- 제목: `fsync` 실패의 의미(규약) 설계: no-trace vs unknown, 그리고 rollback/truncate/프레이밍의 역할 분리
- 작성일: 2026-01-11
- 주제/범위: WAL 설계에서 “`fsync` 실패를 어떻게 해석할지”를 계약으로 명시하고, 그 계약에 따라 필요한 메커니즘(rollback/truncate, 단일 writer/락, 프레이밍)이 어떻게 달라지는지 정리
- 선행지식(필수/권장):
  - 필수: flush vs fsync 의미, 커밋/ack 개념, WAL replay
  - 권장: 동시성(멀티스레드)과 파일 truncate 위험, 멱등성/재시도 설계
- 목표 역량(예: 테스트 설계, 디버깅, 성능 추론, 분산시스템 패턴 적용 등): 커밋 규약/트레이드오프 설계, 실패모드 모델링, 테스트 가능한 계약 정의
- 최종 산출물(코드/문서/실험/데모 링크):
  - 대화 기반 퀴즈/피드백을 실패모드/검증 체크리스트로 정리(이 문서)
  - 참고 구현/데모: `write-ahead-log/src/kv_store.py`, `write-ahead-log/src/wal.py`, `write-ahead-log/scripts/demo_concurrent_rollback_truncation.py`
  - 참고 문서: `write-ahead-log/docs/crash-test-limitations.md`, `write-ahead-log/docs/plan-revision-wal-atomicity.md`
- 난이도(1~5): 4
- 난이도 규약(이 문서에서 사용하는 기준):
  - 1: 개념 1~2개 + 기본 기능 테스트 중심
  - 2: 파일 I/O/포맷이 섞이지만 크래시/동시성은 거의 없음
  - 3: 내구성/복구(replay) + 손상/부분레코드 등 실패모드 포함
  - 4: 계약/의미론(예: `fsync` 실패 의미) 설계가 핵심(테스트/구현 전체에 영향)
  - 5: 분산/합의/복제/정확히 한 번 의미론 등 검증 난이도 높음
- 태그: #storage #durability #fsync #contract #wal #crash #retry #idempotency

## 관련 문서
- Layer 0: `skills/storage/durability-contract/2026-01-11-fsync-failure-contract/layer_0.md`
- Layer 1: `skills/storage/durability-contract/2026-01-11-fsync-failure-contract/layer_1.md`
