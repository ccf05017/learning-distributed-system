# 2계층 산출물 템플릿 (Layer 0 + Layer 1)

## Layer 0: 500자 요약 (압축층)
### 1) 한 줄 요약
- (예) “StarRocks Pipe의 파일 유일성 체크를 테스트로 재현하고, LastModifiedTime 기반 digest의 함정을 회피하는 로딩 전략을 정리했다.”

### 2) 핵심 개념 3개
- 개념1:
- 개념2:
- 개념3:

### 3) 반드시 지켜야 할 불변조건(invariants) 3개
- invariant1:
- invariant2:
- invariant3:

### 4) 흔한 실패/착각 3개
- failure1:
- failure2:
- failure3:

### 5) 다음에 다시 볼 “키워드/검색문”
- (예) “pipe digest lastmodifiedtime duplicate skip”
- (예) “segment file tablet bucket”

---

## 저장/동기화 규칙 (권장)
- 폴더/네이밍
  - `skills/{domain}/{topic}/{YYYY-MM-DD}-{slug}/`
- 파일(주제 폴더 내부)
  - `meta.md`
  - `layer_0.md` (이 문서)
  - `layer_1.md`
  - (선택) `llm_meta.md`
