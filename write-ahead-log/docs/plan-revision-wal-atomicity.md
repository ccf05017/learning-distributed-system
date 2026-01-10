# 계획 변경: Phase 7 WAL 원자성 강화 추가

## 변경 일자
2026-01-10

## 변경 내용
- 기존 Phase 7~11 → Phase 8~12로 번호 조정
- 새로운 Phase 7 "WAL 원자성 강화" 추가

## 배경

### 문제: 비결정적 테스트

Phase 6에서 `test_crash_after_flush_before_fsync_uncertain` 테스트는 비결정적이었다:

```python
# flush 후 fsync 전 크래시
spawn_and_kill(tmp_path, "post_flush", marker_file, "put", "key3", "value3")

# key3는 있을 수도 없을 수도 있음 - OS/파일시스템에 의존
key3_result = store2.get("key3")
print(f"post_flush crash: key3 = {key3_result}")
```

이 상태는 OS 커널 버퍼 동작에 의존하여:
- SIGKILL로 프로세스를 죽여도 OS는 살아있음
- 커널 버퍼가 디스크에 flush될 수도, 안 될 수도 있음
- VM 없이는 정확한 테스트 불가

### 한계의 문서화

`docs/crash-test-limitations.md`에서 이 한계를 문서화했으나, 테스트 자체는 여전히 비결정적으로 남아있었다.

## 제안된 해결책

### 핵심 아이디어: sync 실패 시 WAL 롤백

```python
# Before: append는 반환값 없음
def append(self, record: WALRecord) -> None:
    self._file.write(record.serialize())

# After: append가 offset 반환
def append(self, record: WALRecord) -> int:
    offset = self._file.tell()
    self._file.write(record.serialize())
    return offset

def rollback(self, offset: int) -> None:
    self._file.truncate(offset)
```

sync 실패 시:
```python
offset = self._wal.append(record)
try:
    self._wal.sync()
except IOError:
    self._wal.rollback(offset)  # 방금 쓴 레코드 제거
    raise
```

### 이점

1. **테스트 결정성**: sync 실패 시 WAL에 레코드가 남지 않으므로, 재시작 후에도 key3는 "절대" 복구되지 않음
2. **원자성 명시화**: "커밋 실패 = 레코드 없음"이라는 강력한 계약
3. **실전 패턴 학습**: 실제 DB들(PostgreSQL, SQLite 등)도 유사한 롤백 메커니즘 사용

## 학습 가치 분석

| 측면 | 평가 |
|------|------|
| 비결정적 테스트 해결 | 해결됨 |
| 학습 가치 | WAL 원자성의 핵심 개념 |
| 구현 범위 | 적절함 (offset 반환 + truncate) |
| TDD 적합성 | 테스트 먼저 작성 가능 |

## 새 Phase 7 구성

### 7.1 append가 offset을 반환한다
- append() 호출 시 쓰기 전 파일 위치(offset)를 반환

### 7.2 rollback으로 WAL을 되돌릴 수 있다
- rollback(offset) 호출 시 해당 위치로 파일을 truncate
- rollback 후 다시 append하면 정상 동작

### 7.3 sync 실패 시 자동 롤백
- sync() 실패 시 WAL에 불완전 레코드가 남지 않음
- sync 실패 후 재시작해도 실패한 연산은 복구되지 않음 (결정적)

### 7.4 기존 비결정적 테스트를 결정적으로 전환
- test_crash_after_flush_before_fsync_uncertain → 결정적 테스트로 변경

## 결론

이 변경은 "테스트할 수 없는 것을 문서화"에서 한 단계 나아가, "테스트할 수 있도록 설계를 개선"하는 접근이다. 토이 프로젝트지만 WAL의 핵심 설계 결정을 코드로 명시하는 수준이라 학습에 적합하다.
