# 2계층 산출물 템플릿 (Layer 0 + Layer 1)

## Layer 0: 500자 요약 (압축층)
### 1) 한 줄 요약
- “length-prefix framing은 레코드 경계를 `\\n` 같은 구분자에 의존하지 않고 `[len][payload]`로 고정해, tail partial/프레이밍 충돌을 결정적으로 처리하게 해주며, 체크섬/상한/중단 규칙과 결합하면 파서를 ‘안전하게 실패’하게 만든다.”

### 2) 핵심 개념 3개
- 레코드 경계: 구분자 대신 길이 필드로 payload 범위를 확정
- tail partial: 파일/스트림 끝에서 레코드가 끊기면 “그 레코드는 무시”가 가능해짐
- 파서 방어: 최대 길이 제한 + 무결성 검증 + 중단 정책(prefix 신뢰)

### 3) 반드시 지켜야 할 불변조건(invariants) 3개
- invariant1: `len`은 정책 최대치 이하이며, 남은 바이트보다 크면 해당 지점에서 중단한다
- invariant2: 무결성 검증 실패(체크섬 불일치 등) 시 “침묵 스킵” 대신 명시 정책(대개 중단)을 따른다
- invariant3: 프레이밍은 “파싱 안정성” 레이어이며, 커밋/내구성 의미론(`fsync` 실패 의미 등)을 대신하지 않는다

### 4) 흔한 실패/착각 3개
- failure1: `len`을 신뢰하고 메모리/디스크를 무제한 할당(폭주 length 공격/버그)
- failure2: 손상 레코드를 “그냥 건너뛰고 계속 복구”를 기본값으로 둠(뒤 레코드 해석 신뢰 근거가 없음)
- failure3: 프레이밍을 강화하면 동시성/커밋 의미까지 해결된다고 착각(레이어 혼동)

### 5) 다음에 다시 볼 “키워드/검색문”
- “length-delimited framing crc32 parser hardening”
- “partial record tail truncate stop rule”
- “newline delimited framing binary header newline bug”

