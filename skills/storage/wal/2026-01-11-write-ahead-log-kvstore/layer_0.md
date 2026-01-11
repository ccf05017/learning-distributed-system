# 2계층 산출물 템플릿 (Layer 0 + Layer 1)

## Layer 0: 500자 요약 (압축층)
### 1) 한 줄 요약
- “fsync 완료를 커밋(ack) 기준으로 고정한 WAL 기반 KVStore를 구현하고, 재시작/크래시 타이밍/손상/체크포인트/롤링을 시나리오 테스트로 잠가 ‘무엇이 언제 커밋되는지’를 코드로 학습했다.”

### 2) 핵심 개념 3개
- 커밋 규약: `fsync` 완료 이후만 성공(ack)로 취급
- 복구 규칙: checkpoint 로드 → WAL replay(prefix 신뢰, 손상/부분 레코드에서 안전 중단)
- 스냅샷 패턴: write-tmp-then-rename + 이후 WAL 정리(롤링/트렁케이트)

### 3) 반드시 지켜야 할 불변조건(invariants) 3개
- invariant1: ack는 `fsync` 완료 이후에만 반환한다 (`write-ahead-log/plan.md:95`)
- invariant2: 재시작 복구는 checkpoint → WAL replay 순서이며, replay는 반복 적용해도 최종 상태가 동일해야 한다 (`write-ahead-log/plan.md:190`)
- invariant3: WAL 파싱에서 손상/부분 레코드를 만나면 안전하게 중단하고, 그 이전 prefix까지만 반영한다 (`write-ahead-log/src/wal.py:62`)

### 4) 흔한 실패/착각 3개
- failure1: “SIGKILL이면 전원 차단과 같다” 착각(커널 버퍼는 살아있음) (`write-ahead-log/docs/crash-test-limitations.md:24`)
- failure2: 동시성 실패를 무조건 lock 문제로 단정(포맷/프레이밍 버그일 수 있음) (`write-ahead-log/docs/debugging-lesson-checksum-newline.md:9`)
- failure3: 체크포인트/롤링에서 rename 전후 타이밍을 가볍게 봄(고아 tmp, 중복 적용, 삭제 타이밍) (`write-ahead-log/plan.md:172`)

### 5) 다음에 다시 볼 “키워드/검색문”
- “fsync commit point durability wal replay”
- “write tmp then rename checkpoint crash safe”
- “wal framing newline checksum corruption prefix stop”

