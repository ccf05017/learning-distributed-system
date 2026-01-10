# WAL(Write-Ahead Log) 구현 계획

## 학습 목표
- WAL 기반 단일 노드 KV 스토어를 TDD로 구현하며 분산 시스템의 내구성(durability) 원리를 체득한다
- "로그가 디스크에 안전하게 기록되면 성공(ack)"이라는 커밋 기준을 실험으로 검증한다

---

## Phase 1: 기본 동작 (A 시나리오)
> 메모리 기반 KV 스토어의 기본 CRUD 동작

### 1.1 PUT/GET 기본 (A1)
- [x] 빈 스토어에서 PUT 후 GET으로 값 조회

### 1.2 UPDATE (A2)
- [x] 동일 키에 덮어쓰기 후 최신 값 반환

### 1.3 DELETE (A3)
- [x] 키 삭제 후 존재하지 않음 확인

### 1.4 다중 키 독립성 (A4)
- [x] 여러 키가 서로 독립적으로 동작

---

## Phase 2: WAL 레코드 객체
> 레코드 포맷 정의 및 직렬화/역직렬화 담당

### 2.1 WALRecord 기본 구조
- [x] 레코드 타입을 구분할 수 있다 (PUT, DEL)
- [x] 레코드를 바이트로 직렬화할 수 있다
- [x] 바이트에서 레코드를 역직렬화할 수 있다

### 2.2 레코드 무결성
- [x] 레코드에 체크섬이 포함된다
- [x] 역직렬화 시 체크섬으로 손상 여부를 검증한다
- [x] 손상된 레코드는 오류를 반환한다

### 2.3 레코드 프레이밍
- [x] 레코드가 줄바꿈으로 구분되어 경계를 알 수 있다
- [x] 값에 줄바꿈이 있어도 JSON 이스케이프로 안전하다
- [ ] 부분 레코드(incomplete) 감지 → Phase 3 WAL 읽기에서 처리

---

## Phase 3: WAL 파일 관리 객체
> 파일 I/O 및 레코드 스트림 관리 담당

### 3.1 WAL 쓰기
- [x] 레코드를 파일에 append할 수 있다
- [x] flush/fsync로 디스크에 영구 저장할 수 있다
- [x] 파일을 정상 종료할 수 있다

### 3.2 WAL 읽기
- [x] 파일에서 레코드를 순차적으로 읽을 수 있다
- [x] 손상되거나 불완전한 레코드에서 안전하게 중단한다
  - 빈 줄이 있어도 안전하게 건너뛴다

### 3.3 리소스 관리
- [x] 컨텍스트 매니저 프로토콜 지원 (with 문 사용 가능)

---

## Phase 4: KVStore와 WAL 통합
> 기존 임시 구현을 WAL 객체로 교체

### 4.1 KVStore가 WAL 객체를 사용한다
- [x] PUT 수행 시 WAL 파일에 레코드가 기록된다
- [x] DEL 수행 시 WAL 파일에 레코드가 기록된다
- [x] 정상 종료 시 버퍼의 모든 데이터가 디스크에 flush되고 파일이 닫힌다
- [x] 임시 구현을 WAL 객체로 교체

### 4.2 복구
- [x] 시작 시 WAL에서 레코드를 읽어 상태를 복원한다

---

## Phase 5: 내구성/복구 (B 시나리오)
> 정상 재시작 시 WAL replay로 상태 복구

### 5.1 재시작 후 데이터 유지 (B1)
- [x] PUT 후 재시작 → GET으로 값 확인

### 5.2 여러 업데이트 후 재시작 (B2)
- [x] 동일 키 여러 번 업데이트 후 재시작 → 마지막 값 유지

### 5.3 삭제 후 재시작 (B3)
- [x] DEL 후 재시작 → 삭제 상태 유지

---

## Phase 6: 장애 타이밍 주입 (C 시나리오)
> Write Path 각 단계에서 크래시 시 동작 검증
>
> **커밋 포인트**: fsync 완료 시점. 이전은 미커밋, 이후는 커밋됨.

### 6.1 WAL append 이전 크래시 (C1)
- [x] 크래시 후 재시작 → 데이터 없음

### 6.2 WAL append 후 fsync 전 크래시 (C2)
- [x] 미커밋 상태 → 클라이언트에 실패 전달, 메모리 미반영 (mock)
- [x] append 후 sync 전: Python 버퍼 유실 (SIGKILL)
- [x] flush 후 fsync 전: 불확정 상태 문서화 (SIGKILL 한계)

### 6.3 WAL fsync 후 MemTable 적용 전 크래시 (C3)
- [x] 재시작 후 WAL replay로 복구 (SIGKILL)

### 6.4 MemTable 적용 후 ack 전 크래시 (C4)
- [x] C3와 동치: fsync 완료 = 커밋됨, WAL에서 복구 가능

### 6.5 ack 반환 후 크래시 (C5)
- [x] C3와 동치: 정상 완료 후 크래시, 당연히 복구됨

### 6.6 DEL 장애 타이밍 (C6)
- [x] 삭제 연산에 동일 패턴 적용
  - append 이전 크래시 → 삭제 안 됨
  - fsync 후 크래시 → 삭제 상태 복구

### 테스트 방식
- **Mock 기반**: 특정 시점 실패 시뮬레이션
- **SIGKILL 기반**: subprocess + SIGKILL로 실제 프로세스 종료
  - hook 주입으로 특정 시점에 대기 → SIGKILL로 프로세스 종료
- **한계**: SIGKILL은 프로세스만 죽임. OS 커널 버퍼는 살아있어 flush 후 fsync 전 상태는 정확히 테스트 불가

---

## Phase 7: WAL 원자성 강화
> sync 실패 시 롤백으로 결정적 동작 보장
>
> **배경**: Phase 6에서 flush 후 fsync 전 크래시는 OS 의존적 불확정 상태였음.
> 이를 해결하기 위해 sync 실패 시 WAL을 append 이전으로 롤백하는 메커니즘 추가.

### 7.1 append가 offset을 반환한다
- [x] append() 호출 시 쓰기 전 파일 위치(offset)를 반환한다

### 7.2 rollback으로 WAL을 되돌릴 수 있다
- [x] rollback(offset) 호출 시 해당 위치로 파일을 truncate한다
- [x] rollback 후 다시 append하면 정상 동작한다

### 7.3 sync 실패 시 자동 롤백
- [x] sync() 실패 시 WAL에 불완전 레코드가 남지 않는다
- [x] sync 실패 후 재시작해도 실패한 연산은 복구되지 않는다 (결정적)

### 7.4 결정적 테스트 추가
- [x] mock 기반 결정적 테스트 추가 (test_sync_failure_leaves_no_trace_in_wal)
- [x] SIGKILL 테스트는 OS 레벨 크래시 문서화 목적으로 불확정 유지

---

## Phase 8: WAL 손상/부분 레코드 (D 시나리오)
> 프레이밍/체크섬 검증

### 8.1 Partial record (D1)
- [x] 끝부분 불완전 레코드 무시

### 8.2 체크섬 불일치 (D2)
- [x] 손상 레코드 직전까지만 반영

### 8.3 잘못된 레코드 타입 (D3)
- [x] 포맷 오류 시 중단 (Exception 처리로 통합)

### 8.4 빈 WAL (D4)
- [x] 빈 상태로 복구

---

## Phase 9: 체크포인트/로그 롤링 (E 시나리오)
> 스냅샷 + truncate 안전성
>
> **구현 내용**: checkpoint()가 write-tmp-then-rename 패턴으로 crash-safe하게 동작

### 9.1 체크포인트 후 재시작 (E1)
- [x] checkpoint만으로 복구

### 9.2 체크포인트 후 새 WAL (E2)
- [x] checkpoint + 새 WAL replay

### 9.3 checkpoint.tmp 작성 중 크래시 (E3)
- [x] rename 실패 시 이전 checkpoint 유지 및 tmp 자체 정리
- [x] 시작 시 고아 checkpoint.tmp 청소 (SIGKILL 시나리오)

### 9.4 checkpoint rename 직후 크래시 (E4)
- [x] WAL truncate 전 크래시 → checkpoint + WAL 중복 적용해도 안전 (idempotent)

### 9.5 WAL 삭제 타이밍 크래시 (E5)
- [x] truncate 후 크래시 → checkpoint만으로 복구

---

## Phase 10: 재적용 안전성 (F 시나리오)
> Replay 멱등성 검증
>
> **결과**: PUT/DELETE가 본질적으로 idempotent하므로 추가 구현 없이 통과

### 10.1 동일 WAL 여러 번 replay (F1)
- [x] 매번 동일한 최종 상태

### 10.2 중복 레코드 처리 (F2)
- [x] 중복 PUT도 올바른 결과 (마지막 값이 최종 상태)
- [x] DELETE 후 PUT도 정상 동작

---

## Phase 11: 경계/예외 케이스 (G 시나리오)

### 11.1 빈 키/긴 키/큰 값 (G1)
- [ ] 경계값 테스트

### 11.2 디스크 쓰기 실패 (G2)
- [ ] 실패 시 요청 거부

### 11.3 동시성 (G3) - 선택
- [ ] 멀티 스레드 안전성

---

## Phase 12: 고급 엣지케이스 (H, I, J, K, L 시나리오)

### 12.1 Checkpoint 무결성 (H1, H2)
- [ ] 손상된 checkpoint 폴백

### 12.2 WAL 파서 방어 (I1, I2, I3)
- [ ] 비정상 length, 모순된 필드, 쓰레기 바이트

### 12.3 WAL 세그먼트 롤링 (J1, J2)
- [ ] 롤링 도중 크래시 안전성

### 12.4 ack 의미 강화 (K1, K2)
- [ ] fsync 실패 시 실패 반환, 재시도 안전성

### 12.5 읽기 일관성 (L1) - 선택
- [ ] 동시성 관측값 정의

---

## 진행 방식
1. 각 Phase 내에서 하나의 테스트 케이스를 선택
2. 실패하는 테스트 작성 (Red)
3. 최소한의 코드로 테스트 통과 (Green)
4. 필요시 구조 개선 (Refactor)
5. 커밋 (구조 변경과 동작 변경 분리)
6. 다음 테스트로 진행

---

## 현재 상태
- [x] 프로젝트 환경 세팅 완료 (Python 3.12 + pytest)
- [x] Phase 1 완료 - 메모리 기반 KV Store
- [x] Phase 2 완료 - WAL 레코드 객체
- [x] Phase 3 완료 - WAL 파일 관리 객체
- [x] Phase 4 완료 - KVStore와 WAL 통합
- [x] Phase 5 완료 - 내구성/복구 시나리오
- [x] Phase 6 완료 - 장애 타이밍 주입 (C1~C6)
- [x] Phase 7 완료 - WAL 원자성 강화 (롤백 메커니즘)
- [x] Phase 8 완료 - WAL 손상/부분 레코드
- [x] Phase 9 완료 - 체크포인트/로그 롤링 (write-tmp-then-rename)
- [x] Phase 10 완료 - 재적용 안전성 (idempotent by design)
- [ ] Phase 11 진행 예정 - 경계/예외 케이스
