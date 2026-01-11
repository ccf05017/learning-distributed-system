# 2계층 산출물 템플릿 (Layer 0 + Layer 1)

## Layer 0: 500자 요약 (압축층)
### 1) 한 줄 요약
- “`fsync` 실패를 ‘확정 실패(no-trace)’로 만들지, ‘불확정(unknown)’으로 허용할지(혹은 fatal 처리할지)를 먼저 계약으로 고정해야 하며, rollback/truncate는 그 계약을 강제하는 도구이지 프레이밍(length-prefix/라인)과는 다른 레이어의 문제다.”

### 2) 핵심 개념 3개
- 계약(규약): `fsync` 실패를 성공/실패/불확정 중 무엇으로 해석할지
- ghost commit: 호출 당시 실패로 보였는데 재시작 후 반영되는 현상(불확정 구간의 결과)
- 레이어 분리: 프레이밍(파싱 안정성) vs 커밋 의미(무결한 레코드가 남는 문제)

### 3) 반드시 지켜야 할 불변조건(invariants) 3개
- invariant1: “ack가 성공이면, 재시작 후에도 그 결과는 반드시 보인다”(성공의 의미 고정)
- invariant2: “`fsync` 실패 의미를 계약으로 고정하고, 구현은 그 계약을 깨지 않게 만들어야 한다”
- invariant3: “동시성에서 truncate는 ‘범위 삭제’이므로, 멀티 writer면 배타 제어 없이는 커밋을 날릴 수 있다” (`write-ahead-log/src/wal.py:37`)

### 4) 흔한 실패/착각 3개
- failure1: `fsync` 실패면 “아무 것도 기록되지 않았다”고 단정(실제로는 일부/전부 기록됐을 수도)
- failure2: 프레이밍을 강화하면(`length-prefix` 등) `fsync` 실패 의미까지 해결된다고 착각(레이어 혼동)
- failure3: “깨진 레코드는 스킵하고 계속 복구하면 된다”를 기본값으로 삼음(prefix 신뢰/중단 정책이 더 안전한 경우가 많음)

### 5) 다음에 다시 볼 “키워드/검색문”
- “fsync failed but data persisted ghost commit”
- “durability contract fsync unknown retry idempotency”
- “truncate rollback concurrency lost commit”

