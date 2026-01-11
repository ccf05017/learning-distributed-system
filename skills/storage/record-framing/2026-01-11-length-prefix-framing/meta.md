# 2계층 산출물 템플릿

## 문서 메타
- 제목: 레코드 프레이밍 패턴: length-prefix framing(= length-delimited) + 무결성 검증
- 작성일: 2026-01-11
- 주제/범위: 바이트 스트림(파일/소켓)에서 “레코드 경계”를 안정적으로 정의하기 위한 length-prefix framing 패턴과, partial record/손상 데이터 처리 규칙
- 선행지식(필수/권장):
  - 필수: 바이트/엔디안, 파일 I/O, 예외 처리
  - 권장: 체크섬/CRC, WAL/replay(활용 사례)
- 목표 역량(예: 테스트 설계, 디버깅, 성능 추론, 분산시스템 패턴 적용 등): 바이너리 포맷 설계, 실패모드(부분 쓰기/손상) 모델링, 파서 방어 테스트 설계
- 최종 산출물(코드/문서/실험/데모 링크):
  - 본 문서(패턴 정리)
  - 참고 사례: newline 프레이밍의 함정 회고 `write-ahead-log/docs/debugging-lesson-checksum-newline.md`
- 난이도(1~5): 3
- 난이도 규약(이 문서에서 사용하는 기준):
  - 1: 개념 1~2개 + 기본 기능 테스트 중심
  - 2: 파일 I/O/포맷이 섞이지만 크래시/동시성은 거의 없음
  - 3: 프레이밍/손상/부분 기록 등 파서 방어가 핵심
  - 4: 계약/의미론(예: `fsync` 실패 의미) 설계가 핵심(테스트/구현 전체에 영향)
  - 5: 분산/합의/복제/정확히 한 번 의미론 등 검증 난이도 높음
- 태그: #storage #binary-format #framing #length-prefix #crc #parser-hardening

## 관련 문서
- Layer 0: `skills/storage/record-framing/2026-01-11-length-prefix-framing/layer_0.md`
- Layer 1: `skills/storage/record-framing/2026-01-11-length-prefix-framing/layer_1.md`

