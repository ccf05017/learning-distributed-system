# WAL(쓰기 전 로그) 실습 계획 + BDD 시나리오 기반 테스트 가이드

## 0. 목표
- WAL(Write-Ahead Log) 기반으로 단일 노드 KV 스토어를 구현/분석한다.
- “로그가 디스크에 안전하게 기록되면 성공(ack)”이라는 커밋 기준을 실험으로 검증한다.
- 재시작/장애/손상 상황에서 WAL replay로 상태가 복구됨을 확인한다.
- 체크포인트(스냅샷)와 로그 롤링/삭제(truncate)의 안전성을 검증한다.

---

## 1. 최소 아키텍처(구성 요소)
- **MemTable**: 메모리 Map (key -> value)
- **WAL 파일**: append-only 로그 (PUT/DEL 레코드)
- **Checkpoint(스냅샷) 파일**: MemTable 전체 상태 저장본
- **Recovery**: checkpoint 로드 → WAL을 처음부터 끝까지 replay
- **Truncate/Rolling**: checkpoint 완료 후 이전 WAL 삭제(또는 새 WAL로 롤링)

---

## 2. 처리 흐름(커밋 기준)
### Write Path (PUT/DEL)
1) WAL에 레코드 append  
2) WAL flush/fsync (디스크에 안전하게 기록)  
3) MemTable에 적용  
4) 성공 응답(ack)

### Recovery Path
1) checkpoint 파일이 있으면 로드하여 MemTable 구성  
2) WAL 파일을 처음부터 끝까지 순차 스캔하며 PUT/DEL 적용  
3) 마지막 레코드가 깨졌거나 체크섬이 깨지면 그 지점에서 중단(끝부분은 무시/필요시 truncate)

### Checkpoint & Log Rolling
1) checkpoint.tmp 생성(현재 MemTable 덤프) + fsync  
2) checkpoint로 rename(원자적)  
3) 새 WAL 파일로 교체(롤링)  
4) 이전 WAL 삭제

---

## 3. BDD 스타일 단위테스트(시나리오) 가이드
> 표기: Given / When / Then  
> “크래시”는 프로세스 강제 종료 또는 인위적 실패 주입으로 시뮬레이션한다.  
> “재시작”은 새 인스턴스가 디스크의 checkpoint/WAL을 읽어 복구하는 것을 의미한다.

### A. 기본 동작(정상 시나리오)
#### A1. PUT/GET 기본
- **Given** 빈 스토어
- **When** `PUT(k, v1)` 수행 후 `GET(k)`
- **Then** `GET(k)`는 `v1`을 반환한다

#### A2. UPDATE(덮어쓰기)
- **Given** `PUT(k, v1)`이 완료된 스토어
- **When** `PUT(k, v2)` 수행 후 `GET(k)`
- **Then** `GET(k)`는 `v2`를 반환한다

#### A3. DELETE
- **Given** `PUT(k, v1)`이 완료된 스토어
- **When** `DEL(k)` 수행 후 `GET(k)`
- **Then** `GET(k)`는 존재하지 않음을 반환한다

#### A4. 다중 키 독립성
- **Given** 빈 스토어
- **When** `PUT(k1, v1)`, `PUT(k2, v2)` 수행
- **Then** `GET(k1)=v1`이고 `GET(k2)=v2`다

---

### B. 내구성/복구(정상 재시작)
#### B1. 재시작 후 데이터 유지
- **Given** `PUT(k, v1)`이 완료된 상태
- **When** 프로세스를 정상 종료 후 재시작(Recovery 수행)
- **Then** `GET(k)`는 `v1`을 반환한다

#### B2. 재시작 후 마지막 값 유지(여러 업데이트)
- **Given** `PUT(k, v1)`, `PUT(k, v2)`, `PUT(k, v3)`가 순서대로 완료된 상태
- **When** 재시작
- **Then** `GET(k)`는 `v3`를 반환한다

#### B3. 재시작 후 삭제 유지
- **Given** `PUT(k, v1)` 완료 후 `DEL(k)` 완료
- **When** 재시작
- **Then** `GET(k)`는 존재하지 않음을 반환한다

---

### C. 장애 타이밍 주입(Write Path의 단계별 크래시)
> 목적: “WAL fsync 이후 ack”의 의미를 검증하고, 각 단계에서 어떤 상태가 남는지 확인한다.

#### C1. WAL append 이전 크래시
- **Given** `PUT(k, v1)` 요청이 들어옴
- **When** WAL에 쓰기 전에 크래시
- **Then** 재시작 후 `GET(k)`는 존재하지 않음을 반환한다

#### C2. WAL append 직후(아직 fsync 전) 크래시
- **Given** `PUT(k, v1)` 요청 처리 중
- **When** WAL append는 되었으나 flush/fsync 전에 크래시
- **Then** 재시작 후 `GET(k)`는 **존재하지 않을 수 있다**  
  (커밋 기준이 fsync이므로, 이 상태는 “미커밋”으로 취급됨)

#### C3. WAL fsync 직후(아직 MemTable 적용 전) 크래시
- **Given** `PUT(k, v1)` 요청 처리 중
- **When** WAL fsync는 완료되었으나 MemTable 적용 전에 크래시
- **Then** 재시작 후 WAL replay로 인해 `GET(k)=v1`이어야 한다

#### C4. MemTable 적용 직후(ack 반환 전) 크래시
- **Given** `PUT(k, v1)` 처리 중
- **When** WAL fsync 완료 + MemTable 적용 완료 후 ack 직전에 크래시
- **Then** 재시작 후 `GET(k)=v1`이어야 한다

#### C5. ack 반환 직후 크래시
- **Given** `PUT(k, v1)`이 성공 ack를 반환함
- **When** 바로 크래시 후 재시작
- **Then** `GET(k)=v1`이어야 한다  
  (성공 ack의 의미를 보장)

> DEL에도 동일한 타이밍 주입 케이스를 적용한다(삭제의 내구성 검증).
- C6. `DEL(k)`에서 C1~C5와 동일한 지점 크래시 → 재시작 후 삭제 여부가 커밋 규칙에 맞게 반영되어야 함

---

### D. WAL 손상/부분 레코드(프레이밍/체크섬 검증)
#### D1. 파일 끝 부분 레코드가 “중간에서 끊김”(partial record)
- **Given** 여러 개의 정상 레코드가 있는 WAL
- **When** 마지막 레코드가 중간까지만 기록된 상태로 크래시 후 재시작
- **Then** 복구는 “마지막 완전한 레코드”까지만 반영되고,
  끊긴 마지막 레코드는 무시되어야 한다

#### D2. 체크섬 불일치(내용 변조/손상)
- **Given** 정상 WAL이 존재
- **When** 특정 레코드의 payload 일부가 변경되어 checksum mismatch 발생
- **Then** 복구는 “손상 레코드 직전까지”만 반영하고,
  손상 레코드 및 이후는 무시(또는 중단)되어야 한다

#### D3. 잘못된 레코드 타입/버전(포맷 오류)
- **Given** WAL에 정의되지 않은 타입 또는 버전이 등장
- **When** 재시작 복구
- **Then** 해당 지점에서 복구를 중단하고, 그 이전까지는 정상 반영되어야 한다

#### D4. WAL이 비어있거나(0바이트) 레코드가 0개인 경우
- **Given** checkpoint는 없고 WAL만 존재(0바이트 또는 레코드 없음)
- **When** 재시작 복구
- **Then** 스토어는 빈 상태여야 한다

---

### E. 체크포인트/로그 롤링(스냅샷 + truncate) 안전성
#### E1. 체크포인트 후 재시작(로그 없이도 복구)
- **Given** 여러 PUT/DEL이 수행된 후 checkpoint가 완료되었고, 이전 WAL이 삭제됨
- **When** 재시작
- **Then** checkpoint 상태로 MemTable이 복구되어야 한다

#### E2. 체크포인트 직후 새 WAL 롤링 검증
- **Given** checkpoint 완료 후 새 WAL로 전환된 상태
- **When** 추가로 `PUT(k, v_new)` 수행 후 재시작
- **Then** checkpoint + 새 WAL replay 결과가 반영되어 `GET(k)=v_new`가 되어야 한다

#### E3. checkpoint.tmp 작성 중 크래시(rename 이전)
- **Given** checkpoint 수행 중이며 checkpoint.tmp에 일부만 기록된 상태
- **When** 크래시 후 재시작
- **Then** (1) 이전 checkpoint가 있다면 그것을 사용하고,
  (2) WAL replay로 최신 상태로 복구되어야 한다  
  (checkpoint.tmp는 무시되어야 한다)

#### E4. checkpoint rename 직후 크래시(새 checkpoint는 존재)
- **Given** checkpoint.tmp → checkpoint rename이 완료된 직후
- **When** 크래시 후 재시작
- **Then** checkpoint는 유효하게 로드되어야 하고, WAL replay로 일관된 최종 상태가 되어야 한다

#### E5. WAL 삭제/트렁케이션 타이밍 크래시 안전성
- **Given** checkpoint가 완료되고 이전 WAL을 삭제하거나 truncate하려는 시점
- **When** (A) 삭제 직전 크래시, (B) 삭제 직후 크래시 각각 재시작
- **Then**
  - (A) WAL이 남아있어도 checkpoint + WAL replay로 정상 상태여야 한다
  - (B) WAL이 없어도 checkpoint만으로 정상 상태여야 한다

---

### F. 재적용 안전성(Replay의 반복 적용)
> “항상 처음부터 끝까지 replay” 설계에서는 특히 중요.

#### F1. 동일 WAL을 여러 번 replay해도 결과 동일(멱등성 요구)
- **Given** checkpoint 없이 WAL만으로 복구 가능한 상태
- **When** 재시작을 연속으로 여러 번 수행(매번 처음부터 끝까지 replay)
- **Then** 매번 동일한 최종 상태를 얻어야 한다

#### F2. 중복 레코드(같은 PUT이 연속) 처리
- **Given** `PUT(k, v1)`이 여러 번 연속 기록된 WAL
- **When** 재시작 복구
- **Then** 최종적으로 `GET(k)=v1`이어야 한다 (중복 적용이 결과를 망치지 않아야 함)

---

### G. 경계/예외 케이스(필수 검증)
#### G1. 빈 키/긴 키/큰 값(포맷 경계)
- **Given** 키/값 길이가 경계값(0, 매우 큼 등)에 가까운 입력
- **When** PUT 후 재시작 복구
- **Then** 포맷이 깨지지 않고 동일 값이 복구되어야 한다  
  (정책상 허용하지 않는 입력은 “명확한 오류”로 거부되어야 한다)

#### G2. 디스크 부족/쓰기 실패(내구성 위반 방지)
- **Given** WAL append 또는 fsync가 실패하는 환경(실패 주입)
- **When** `PUT/DEL` 수행
- **Then** 요청은 실패로 처리되어야 하며, 재시작 후에도 “성공한 것처럼” 보이면 안 된다

#### G3. 동시성(멀티 스레드) 기본 안전성(선택)
- **Given** 여러 스레드가 동시에 PUT/DEL 호출
- **When** 일정 시간 작업 후 재시작 복구
- **Then** (정의한 직렬화 규칙에 따라) 데이터 손상 없이 복구되어야 한다  
  (처음 실습에서는 단일 스레드로 제한해도 됨)

---

## 4. (추가) 누락 가능 엣지케이스 / 학습 중요 시나리오

### H. Checkpoint 무결성 및 선택(폴백) 로직
#### H1. Checkpoint 파일 손상 시 폴백
- **Given** checkpoint 파일이 존재하지만 무결성 검증(예: 체크섬/포맷 검증)에 실패한다
- **When** 재시작 복구를 수행한다
- **Then** 손상된 checkpoint를 사용하지 않고(또는 이전 checkpoint가 있으면 이전 것을 선택하고) WAL 기반으로 가능한 만큼 복구되어야 한다

#### H2. 최신 Checkpoint처럼 보이지만 내용이 불완전한 경우
- **Given** checkpoint 파일명이 최신이지만 내부 레코드가 partial/불완전하여 로드에 실패한다
- **When** 재시작 복구를 수행한다
- **Then** checkpoint 로드는 실패로 처리되고, 폴백 규칙에 따라 WAL(또는 이전 checkpoint + WAL)로 복구되어야 한다

---

### I. WAL 파서 방어(손상 형태 다양화)
#### I1. 비정상 length(폭주) 방어
- **Given** WAL 레코드의 length 필드가 정책 최대치 초과 또는 파일 크기/남은 바이트보다 큰 값이다
- **When** 재시작 복구가 WAL 스캔 중 해당 레코드를 만난다
- **Then** 해당 지점에서 복구를 중단하고, 그 이전의 정상 레코드까지만 반영되어야 한다

#### I2. 내부 길이 필드 모순(keyLen/valueLen 등)
- **Given** WAL 레코드는 프레이밍상으로 읽히지만 payload 내부의 길이 필드가 payload 범위를 초과하거나 서로 모순된다
- **When** 재시작 복구가 해당 레코드를 파싱한다
- **Then** 해당 레코드부터 복구를 중단(또는 무시)하고, 이전까지는 정상 반영되어야 한다

#### I3. 정상 레코드 뒤 “쓰레기 바이트”가 붙은 경우
- **Given** 여러 정상 레코드가 끝난 뒤, 의미 없는 바이트가 WAL 파일 끝에 추가되어 있다
- **When** 재시작 복구가 WAL 끝부분을 읽는다
- **Then** 마지막 정상 레코드까지만 반영되고, 쓰레기 바이트는 무시/중단 처리되어야 한다

---

### J. WAL 세그먼트 롤링/삭제 경계 크래시
#### J1. WAL 롤링 도중 크래시(전환 경계)
- **Given** wal-0001에서 wal-0002로 전환(롤링)하는 시점이다
- **When** 다음 중 하나의 지점에서 크래시 후 재시작한다  
  - (A) 새 WAL 파일(wal-0002) 생성 직후  
  - (B) “현재 WAL 포인터”가 wal-0002로 전환된 직후  
  - (C) 이전 WAL(wal-0001) 삭제 직후
- **Then** 어떤 경우에도 재시작 복구 결과가 일관되어야 하며, 커밋된 작업은 유지되고 미커밋 작업은 나타나면 안 된다

#### J2. Checkpoint 존재 + WAL 세그먼트 조합이 비정상인 경우
- **Given** checkpoint는 존재하지만 WAL 세그먼트 파일이 일부만 남아있다(예: wal-0001은 삭제되고 wal-0002만 존재, 혹은 반대)
- **When** 재시작 복구를 수행한다
- **Then** 파일 선택 규칙(예: 번호 순, 메타데이터)에 따라 올바른 세그먼트만 읽어 복구해야 하며, 누락/중복 적용이 발생하면 안 된다

---

### K. ack(성공 응답) 의미 강화 시나리오
#### K1. fsync 실패 시 “성공처럼 보이면 안 됨”
- **Given** WAL fsync가 실패하도록 실패 주입되어 있다
- **When** `PUT/DEL`을 수행한다
- **Then** API는 실패를 반환해야 하고, 재시작 후에도 해당 변경이 반영된 것처럼 보이면 안 된다

#### K2. ack 유실(클라이언트 타임아웃) → 동일 요청 재시도
- **Given** 서버는 WAL fsync까지 완료하고 내부적으로 성공 처리했지만, 클라이언트는 응답을 받지 못해 타임아웃이 발생한다
- **When** 클라이언트가 동일 요청을 재전송(재시도)한다
- **Then** 재시도가 시스템 상태를 깨뜨리지 않아야 하며(중복 기록으로 잘못된 상태가 되지 않아야 함), 최종 상태는 “한 번 성공한 것”과 동일해야 한다

---

### L. (선택) 읽기 일관성 관찰 시나리오(동시성)
#### L1. PUT 처리 중 GET 관측값 정의
- **Given** `PUT(k, v_new)`가 처리 중이며 단계별로 멈출 수 있다(예: fsync 전/후, MemTable 적용 전/후)
- **When** 다른 실행 흐름에서 `GET(k)`를 수행한다
- **Then** 시스템이 목표로 하는 일관성 규칙에 맞는 값만 관측되어야 한다  
  (예: ack 이전에는 old 또는 not-found만, ack 이후에는 new가 반드시 보임 등)

