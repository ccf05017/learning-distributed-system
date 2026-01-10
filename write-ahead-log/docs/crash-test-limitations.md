# 크래시 테스트 한계 및 설계 결정

## 배경

WAL 기반 KV Store의 내구성을 검증하기 위해 Write Path 각 단계에서 크래시 시나리오를 테스트하려 했다.

```
PUT 요청 → append() → flush() → fsync() → _apply_record() → ack
              ↑          ↑         ↑
             C1         C2        C3 (커밋 포인트)
```

## 문제: flush 후 fsync 전 크래시 (C2b)

### 상태 정의

- `flush()`: Python 버퍼 → OS 커널 버퍼
- `fsync()`: OS 커널 버퍼 → 물리 디스크

flush 후 fsync 전에 크래시가 발생하면:
- 데이터는 OS 커널 버퍼에 있음
- 디스크에 기록됐는지는 **OS에 의존**

### 시도 1: SIGKILL

```python
os.kill(proc.pid, signal.SIGKILL)
```

**결과**: 프로세스만 죽고 OS는 계속 실행됨. 커널 버퍼가 살아있어 데이터가 디스크에 기록될 수 있음.

**한계**: 전원 차단 시뮬레이션 불가.

### 시도 2: Testcontainers (Docker)

계획:
1. 호스트에서 WAL 경로 생성
2. 컨테이너에 bind mount
3. 컨테이너 내에서 hook 기반으로 특정 시점에 대기
4. 호스트에서 컨테이너 강제 종료
5. WAL 파일 상태 확인

**분석**:
```
컨테이너 프로세스 → Python 버퍼 → [flush] → 호스트 커널 버퍼 → [fsync] → 디스크
                                              ↑
                                    bind mount는 호스트 파일시스템 직접 사용
```

Bind mount 사용 시 쓰기는 호스트 파일시스템을 통해 이루어짐. 컨테이너를 죽여도 호스트 OS는 계속 실행되므로 커널 버퍼가 살아있음.

**결론**: SIGKILL과 동일한 한계.

### 시도 3: VM 강제 종료

Vagrant/QEMU로 VM을 실행하고 VM 자체를 강제 종료하면 진짜 전원 차단을 시뮬레이션할 수 있음.

**결론**: 가능하지만 테스트 복잡도 대비 학습 가치가 낮다고 판단.

## 설계 결정

### 결정: C2b (flush 후 fsync 전)는 불확정 상태로 문서화

**근거**:
1. 이 상태는 정의상 "OS에 의존"하는 불확정 상태
2. 실제 시스템에서도 이 구간은 내구성 보장 불가
3. 커밋 포인트가 fsync인 이유가 바로 이것
4. 테스트로 "보장됨"을 증명할 수 없으면, "보장 안 됨"을 문서화하는 것이 정직함

### 현재 테스트 구조

```
C1: append 전 크래시 → 데이터 없음 (검증 가능)
C2: append 후 fsync 전 크래시
    - sync 실패 시 예외 발생 (mock으로 검증)
    - append 후 flush 전: Python 버퍼 유실 (SIGKILL로 검증)
    - flush 후 fsync 전: 불확정 (SIGKILL 한계로 결과만 출력)
C3: fsync 후 크래시 → WAL replay로 복구 (검증 가능)
```

### 테스트 코드에서의 처리

```python
def test_crash_after_flush_before_fsync_uncertain(self, tmp_path):
    """C2-sigkill. flush 후 fsync 전 크래시 → 불확정 상태
    SIGKILL은 OS를 죽이지 않으므로 OS가 버퍼를 flush할 수 있음.
    이 테스트는 SIGKILL 한계와 불확정 상태를 문서화.
    """
    # ... 테스트 코드 ...

    # key3는 있을 수도 없을 수도 있음 - OS/파일시스템에 의존
    key3_result = store2.get("key3")
    print(f"post_flush crash: key3 = {key3_result}")
```

단정문(assert) 없이 결과만 출력하여 "불확정"임을 표현.

## 핵심 교훈

1. **커밋 포인트의 의미**: fsync가 커밋 포인트인 이유는 그 전까지는 내구성을 보장할 수 없기 때문
2. **테스트의 한계**: 일부 시나리오는 특수 환경(VM, 하드웨어) 없이는 정확히 테스트 불가
3. **정직한 문서화**: 테스트할 수 없는 것을 테스트하는 척하지 않고, 한계를 명시하는 것이 더 가치있음
