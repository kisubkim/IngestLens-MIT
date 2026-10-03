# HANDOFF: 다른 환경에서 이어서 개선하기 위한 문서

최종 갱신: 2026-10-03. 이 문서는 현재 상태, 새 환경 준비, 실제 모델 연결 절차, 튜닝 방법, 남은 일, 개발 중 겪은 함정을 정리한다.
원래 계획은 `docs/PLAN.md`, 평가 방법은 `evals/README.md`에 있다.

---

## 1. 한눈에 보기

**무엇**: 웹에서 문서를 올리면 6개 agent가 LangGraph 파이프라인으로 처리한다. 형식 판별 → 페이지 성격 분석 → 파서·청킹 전략 결정 → 파싱(VLM 포함) → 청킹 → 임베딩(Qdrant). 모든 자동 결정의 근거(규칙, 입력값, 대안, 신뢰도)를 저장하고 웹 화면에 보여준다.

**대상 환경**: 직접 운영하는 서버. 외부 API를 쓰지 않고 직접 띄운 vLLM(OpenAI 호환 API)만 호출하므로 인터넷이 없는 환경에서도 동작한다.

| 마일스톤 | 상태 | 내용 |
|---|---|---|
| M1 골격 | 완료 | FastAPI, SQLite, LangGraph, SSE, 진행 화면, 텍스트 PDF 전체 경로 |
| M2 분석·전략 | 완료 | 페이지 feature, 규칙 분류, VLM 2차 판단, 결정 근거, 파싱 리포트 화면 |
| M3 VLM 파싱 | 완료 | OCR, 그림 영역 설명, 캡션 연결, 표 재추출, 프로세스 풀, 150MB 벤치마크, 실행 취소 |
| M4 Office | 완료 | LibreOffice 경로와 자체 렌더링 경로, 헤딩·노트·차트 데이터 힌트, 시트 표 헤더 반복 |
| M5 결과 화면 | 완료 | 청크, 임베딩(PCA, 이웃), 검색(dense/BM25/hybrid, rerank, 단계별 점수) |
| M6 튜닝 | 도구만 완료 | 평가 스크립트, 합성 세트, `/tokenize` 토큰 보정, `table_text_share` 규칙. 실제 데이터 튜닝은 남음 |

### 검증 수준: 이어받는 사람이 가장 먼저 알아야 할 것

| 항목 | 검증 방법 | 실제 환경 검증 |
|---|---|---|
| 파이프라인 전체, UI 6개 탭, 여러 파일 순차 실행, HTTP 수집 API, 저장 위치 설정 | 백엔드 테스트 46개, Edge 화면 캡처(순차 실행·설정 화면 UI는 빌드만 확인) | 개발 PC(Windows)에서만 |
| VLM (OCR, 그림, 표, 분류) | 코드 mock, `scripts/mock_vllm.py` HTTP mock | **실제 VL 모델로 검증 안 함**. prompt 응답 형식이 맞는지 모름 |
| 임베딩 | dev-hash, mock HTTP | **실제 임베딩 모델로 검증 안 함** |
| reranker, `/tokenize` | mock HTTP | 실제 vLLM으로 검증 안 함 |
| LibreOffice 변환 | 가짜 변환 함수(테스트) | **LibreOffice로 실제 변환해 본 적 없음** (개발 PC에 미설치) |
| Office 자체 렌더링 | 생성한 docx/pptx/xlsx | 실제 문서로 검증 안 함 |
| 150MB 대용량 | 합성 PDF (노이즈 이미지) + mock VLM | 실제 문서, 실제 VLM으로 측정 안 함 |
| Linux(운영 서버) | 없음 | **Windows에서만 실행해 봄** |

---

## 2. 폴더 지도

```
IngestLens/
  backend/app/
    agents/     intake, profiler, strategy, parser, chunker, embedder, retriever (+ common)
    graph/      pipeline.py: LangGraph 정의, 실행/취소
    api/        documents, runs(이벤트·SSE·결정·페이지·요소·청크·임베딩·이웃), search, ingest(외부 수집·Open WebUI 로더), settings(저장 위치), auth
    tools/      pdf, figures, office, office_native, vlm, vlm_output, embedding, reranker, lexical, chunking, vectorstore
    models.py   Document, Run, Event, Decision, PageProfile, Element, Chunk
    events.py   emit_event / record_decision + SSE fan-out
  backend/tests/   pytest 46개 (conftest의 합성 PDF, office_fixtures)
  config/     models.yaml (모델 endpoint), strategy_rules.yaml (모든 규칙과 파라미터)
  frontend/   React + Vite. build 결과물 dist/는 FastAPI가 / 경로로 서빙
  scripts/    mock_vllm, bench_large, make_eval_set, eval_profile, eval_retrieval, _inproc
  evals/      synthetic/ (합성 평가 세트), reports/ (측정 보고서), README.md
  docs/       PLAN.md, HANDOFF.md (이 문서)
```

---

## 3. 새 환경에서 시작하기

### 3-1. 개발 PC (인터넷 가능)

```bash
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements-dev.txt     # Linux: .venv/bin/pip
cd frontend && npm install && npm run build && cd ..
cd backend && ../.venv/Scripts/python -m pytest -q             # 46 passed 확인
../.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

### 3-2. 오프라인 환경 반입

인터넷이 되는 PC에서 준비한다.

```bash
# (1) Python wheel. 운영 서버의 OS/CPU/Python 버전에 맞춘다. 예: Linux x86_64, Python 3.12
pip download -r backend/requirements.txt -d wheelhouse \
  --platform manylinux2014_x86_64 --platform manylinux_2_28_x86_64 \
  --python-version 3.12 --only-binary=:all:
# (2) 프론트엔드는 빌드 결과물만 반입한다. 운영 서버에 Node.js가 필요 없다.
cd frontend && npm ci && npm run build        # frontend/dist 를 반입
# (3) 소스 반입. 제외: .venv, frontend/node_modules, data, __pycache__
```

운영 서버에서 설치한다.

```bash
python3.12 -m venv .venv
.venv/bin/pip install --no-index --find-links wheelhouse -r backend/requirements.txt
cd backend && ../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- **LibreOffice(선택)**: 없어도 docx/pptx/xlsx는 자체 렌더링으로 처리된다. doc/ppt/hwp를 처리하거나 원본 레이아웃이 필요할 때만 설치한다. 설치 후 `RAG_SOFFICE_PATH`를 지정하거나 PATH에 추가한다.
- **한글 폰트**: 자체 렌더링은 PyMuPDF 내장 CJK 폰트를 쓰므로 필요 없다. LibreOffice를 쓴다면 서버에 한글 폰트(나눔 등)를 설치해야 변환 결과가 깨지지 않는다.
- **데이터 위치**: `RAG_DATA_DIR`(기본 `./data`)에 업로드 원본, 변환 PDF, 페이지 이미지 캐시, SQLite, 내장 Qdrant가 저장된다. 백업 대상이다.
- **확인 필요**: Linux에서 실행해 본 적이 없다. 두 가지를 확인한다.
  - `ProcessPoolExecutor`: Linux 기본값인 fork 방식에서 문제없는지
  - 경로 처리

### 3-3. 모델 준비 (vLLM)

`config/models.yaml`의 `base_url`만 채우면 된다. 비워 두면 해당 기능은 대체 동작(fallback)하고, 그 사실이 결정 기록으로 남는다.

| 용도 | 권장 모델 | vLLM 실행 예 | 쓰는 API |
|---|---|---|---|
| VLM (필수 권장) | Qwen2.5-VL 7B 급 | `vllm serve Qwen/Qwen2.5-VL-7B-Instruct` | `/v1/chat/completions` (이미지 data URL) |
| 임베딩 (필수) | BAAI/bge-m3 (한국어, 8192 토큰) | `vllm serve BAAI/bge-m3 --task embed` ※ | `/v1/embeddings`, `/tokenize` |
| reranker (선택) | BAAI/bge-reranker-v2-m3 | `vllm serve BAAI/bge-reranker-v2-m3 --task score` ※ | `/v1/rerank` |

※ vLLM 버전에 따라 pooling 모델 실행 옵션 이름이 다르다(`--task` 또는 `--runner pooling` 계열). 설치된 버전의 문서를 확인한다.

**개발 PC에서 간단히 쓰려면 Ollama**(설치되어 있음, 모델은 없음):
- `ollama pull bge-m3`을 실행하고 `embedding.base_url: http://localhost:11434/v1`, `model: bge-m3`로 설정한다.
- VL 모델은 `ollama pull qwen2.5vl:7b`를 쓴다.
- Ollama에는 `/tokenize`와 `/rerank`가 없다. 그래서 토큰 비율은 기본값 2.5를 쓰고 rerank는 꺼진다. 이 사실도 결정 기록으로 남는다.

**GPU 없이 흐름만 확인**: `python scripts/mock_vllm.py --port 8001`을 실행하고 모든 `base_url`을 `http://127.0.0.1:8001/v1`로 설정한다.

### 3-4. Open WebUI 연동 (선택)

Open WebUI에 파일을 추가하면 이 서버가 파일을 받아 파이프라인을 자동으로 실행하게 할 수 있다. Open WebUI의 **External 문서 로더**(콘텐츠 추출 엔진) 기능을 쓴다. Open WebUI 쪽에는 코드 수정이나 플러그인이 필요 없다.

**이 서버 설정** (`.env` 또는 환경 변수)

```bash
RAG_API_KEY=<임의의 긴 문자열>        # Open WebUI가 보내는 Bearer 키. 비우면 인증 없이 받는다
RAG_INGEST_WAIT_SECONDS=3600          # 실행 완료를 기다리는 최대 시간(초). 넘으면 504
```

Open WebUI 서버에서 이 서버의 포트(기본 8000)에 접속할 수 있어야 한다. 그래서 `--host 0.0.0.0`으로 실행한다.

**Open WebUI 설정**: 관리자 화면이나 환경 변수 중 하나로 설정한다.

| 관리자 화면 (관리자 설정 → 문서) | 환경 변수 | 값 |
|---|---|---|
| 콘텐츠 추출 엔진 | `CONTENT_EXTRACTION_ENGINE` | `External` (환경 변수는 `external`) |
| URL | `EXTERNAL_DOCUMENT_LOADER_URL` | `http://<이 서버 주소>:8000/api/openwebui` (끝에 `/process`를 붙이지 않는다. Open WebUI가 붙인다) |
| API 키 | `EXTERNAL_DOCUMENT_LOADER_API_KEY` | 위 `RAG_API_KEY`와 같은 값 |

**동작**
1. Open WebUI가 `PUT {URL}/process`를 호출한다. 본문은 파일 바이트이고, 헤더는 `X-Filename`(URL 인코딩된 파일 이름), `Content-Type`, `Authorization: Bearer <키>`다.
2. 이 서버는 파일을 저장하고 실행을 대기열에 넣는다. 화면에서 시작한 실행과 같은 줄이라 하나씩 순서대로 처리된다. 같은 파일(sha256)의 성공한 실행이 있으면 다시 실행하지 않는다.
3. 실행이 끝나면 청크를 `[{page_content, metadata}]`로 돌려준다. metadata는 `source`(파일 이름), `document_id`, `run_id`, `chunk_id`, `page`(1부터), `pages`, `section`, `element_types`이고 모두 문자열이나 숫자다.
4. Open WebUI는 받은 청크를 자기 임베딩으로 다시 색인한다. 이 서버의 Qdrant에도 같은 문서가 색인되며, 처리 과정과 결정 근거는 이 서버 화면에서 볼 수 있다.

**연결 확인 순서**
1. Open WebUI 서버에서 `curl -X PUT -H "Authorization: Bearer <키>" -H "X-Filename: test.pdf" --data-binary @test.pdf http://<이 서버>:8000/api/openwebui/process`를 실행해 JSON 배열이 오는지 본다. 401이면 키가, 연결 오류면 방화벽이나 host 설정이 문제다.
2. Open WebUI에서 작은 PDF를 지식 베이스나 채팅에 추가한다. 이 서버 화면의 문서 목록에 나타나고 `succeeded`가 되는지 본다.
3. 큰 문서로 timeout을 확인한다. Open WebUI는 이 서버가 응답할 때까지 업로드 처리를 기다린다. 중간에 reverse proxy(nginx 등)가 있으면 `proxy_read_timeout`을 처리 시간보다 길게 잡는다.

**오류 응답**: 지원하지 않는 형식 등으로 실행이 실패하면 502이고 detail에 실행 오류가 들어간다. 대기 시간을 넘기면 504, 빈 파일은 400이다. Open WebUI에는 파일 처리 실패로 보인다.

범용 HTTP 수집(`POST /api/ingest`, multipart, 등록만 하고 바로 응답)은 README "HTTP 수집 API"를 본다.

---

## 4. 실제 모델을 연결한 뒤 첫 검증 순서

1. `models.yaml`을 설정하고 서버를 재시작한다.
2. 검색 화면 capabilities에 임베딩 모델과 reranker 이름이 보이는지 확인한다.
3. 문서 1개를 실행하고 "진행 현황 → 결정 로그"에서 다음을 확인한다.
   - `token estimate`가 `tokenizer_calibrated`(측정값)인지. `default`면 `/tokenize` 경로를 확인한다. `embedding.base_url`의 `/v1` 앞 주소에 `/tokenize`가 있어야 한다.
   - `embedding model`이 dev-hash가 아닌지.
4. 스캔 페이지와 그림 페이지가 있는 문서로 **VLM 응답 형식**을 확인한다. 파싱 리포트에서 다음을 본다.
   - 그림 element의 `figure_type` 태그가 chart/diagram 등으로 붙는지. 답의 첫 줄 `TYPE:` 규약을 모델이 지키는지 보는 것이다. 안 지키면 전부 `diagram`이 된다.
   - OCR 결과가 제목, 본문, 표로 나뉘는지. 모델이 Markdown `#` 헤딩을 쓰는지 보는 것이다.
   - 경고/오류 탭에 `truncated at max_tokens`가 뜨면 `vlm.max_tokens`를 올린다.
   - prompt를 고치면 `tools/vlm_output.py`의 파서와 `scripts/mock_vllm.py`도 함께 고친다.
5. 평가 기준선을 측정한다: `scripts/eval_retrieval.py --models <실제 models.yaml>`. 합성 세트의 바꿔 쓴 질의(paraphrase) 점수가 dev-hash의 62%(hybrid hit@1)보다 크게 오르는지 본다.
6. 속도를 측정한다: `scripts/bench_large.py --vlm-url <실제 VLM>`. VLM 1회 평균 시간과 `vlm.max_concurrency`를 조정한다. GPU 여유를 보면서 올린다.

---

## 5. 튜닝 방법 (M6 도구)

자세한 형식은 `evals/README.md`에 있다. 요약하면 다음과 같다.

1. **실제 문서로 평가 세트를 만든다**. 문서 5~20개, 페이지 라벨, 질의 20~50개가 필요하다. 가장 효과가 큰 작업이다.
2. `eval_profile.py --sweep`: 틀린 페이지와 feature 값을 보고 규칙을 고친다.
   - sweep 제안을 그대로 쓰지 말고, 새 feature나 규칙을 만드는 쪽을 먼저 생각한다.
   - 예: 작은 표 페이지 문제는 임계값을 낮추는 대신 `table_text_share` feature와 규칙을 추가해서 해결했다.
3. `eval_retrieval.py`: 청킹 크기(`strategy.target_tokens`), 모드, 가중치, rerank를 **하나씩** 바꾸며 비교한다.
4. 좋아진 변경은 `config/strategy_rules.yaml`에 반영한다. 규칙 변경은 `tests/test_profiler.py`에 회귀 테스트로 남긴다.
5. 측정 결과를 아래 7절 표에 추가한다.

튜닝 후보:
- `profiler.rules`의 임계값: 특히 슬라이드는 글자가 적어 `mixed`로 분류되고 VLM 2차 판단이 늘어날 수 있다.
- `vlm_review_below` / `vlm_review_max_pages`
- `parse.figures.min_area_ratio`: 작은 아이콘이 그림으로 잡히는지 확인한다.
- `captions.pattern`
- `tables.max_empty_cell_ratio`
- `strategy.target_tokens` / `overlap_tokens`
- `section_min_page_ratio`

---

## 6. 남은 일 (우선순위)

**P0: 실제 환경 반입 직후**
- [ ] 4절 체크리스트로 실제 VLM, 임베딩, reranker를 연결하고 검증한다.
- [ ] Linux에서 실행을 확인한다(프로세스 풀, 경로, 권한).
- [ ] **인증과 접근 제어**가 없다. 내부 네트워크에서만 쓰더라도 접속할 수 있는 누구나 업로드, 조회, 검색할 수 있다. 배포 전에 최소한 SSO나 reverse proxy 인증을 붙인다.
- [ ] Open WebUI 연동(`PUT /api/openwebui/process`)을 실제 Open WebUI로 검증한다. 규약은 Open WebUI 소스(`retrieval/loaders/external_document.py`)를 보고 맞췄고 테스트는 TestClient로만 했다. 로더는 실행이 끝날 때까지 응답을 잡고 있으므로, 큰 문서에서 Open WebUI 쪽 요청 timeout과 reverse proxy timeout을 확인한다.
- [ ] LibreOffice를 쓴다면 실제 변환을 검증한다. 한글 폰트, 슬라이드 1장 = 1페이지인지(노트 페이지 출력 옵션이 꺼져 있는지) 확인한다.

**P1: 품질**
- [ ] 실제 문서로 평가 세트를 만들고 기준선을 측정한다.
- [ ] 짧은 청크를 병합한다. 현재 섹션이 짧으면 `too_short` 청크가 많이 생긴다. 최소 크기에 못 미치면 같은 섹션 안의 다음 청크와 합치는 방식이다.
- [ ] 스캔 OCR 결과의 위치 정보: 지금은 모든 element가 페이지 전체 bbox를 갖는다. VLM grounding 출력이나 OCR 엔진 bbox로 개선한다.
- [ ] 자체 렌더링의 누락 항목을 보강한다: docx 머리글/바닥글/각주/텍스트 상자, pptx SmartArt·도형 텍스트 일부.
- [ ] 문서와 run 삭제 API 및 UI가 없다. 현재는 data 폴더를 직접 지워야 한다.

**P2: 기능과 확장**
- [ ] 검색 결과로 LLM 답변 생성과 인용(텍스트 LLM endpoint 추가)
- [ ] 여러 서버 인스턴스로 확장: Qdrant 서버(`RAG_QDRANT_URL`), PostgreSQL(`RAG_DB_URL`), 작업 큐(arq 등)
- [ ] 임베딩 2D 투영을 UMAP으로 바꾸고 겹친 점을 구분한다(현재 PCA).
- [ ] HWP 자체 처리 (현재는 LibreOffice 필요)
- [ ] BM25 영어 어간 처리, 불용어 처리

---

## 7. 측정 기록

| 날짜 | 조건 | 결과 | 비고 |
|---|---|---|---|
| 2026-09-30 | 150MB/300p 합성 PDF, mock VLM 0.3s, 동시 4, 스레드 방식 | 파싱 43.7s (준비 41.9s) | PyMuPDF가 GIL을 잡아 스레드 병렬이 효과 없음 |
| 2026-09-30 | 같은 조건, 프로세스 풀 workers 4 | 전체 25.4s, 파싱 19.9s, 최대 1.1GB(worker 포함) | VLM 200회, 오류 0 |
| 2026-09-30 | 같은 PDF, VLM 없음 | 전체 5.6s, 최대 0.6GB | |
| 2026-09-30 | 합성 세트 페이지 분류(12p) | 91.7% → 100% | `table_text_share` 규칙 추가 후 |
| 2026-09-30 | 합성 세트 검색 22문항, dev-hash | hybrid hit@1 82% (lexical 93%, paraphrase 62%) | 실제 임베딩 연결 후 비교 기준 |

---

## 8. 설계 결정과 이유

| 결정 | 이유 | 다시 생각할 조건 |
|---|---|---|
| 모든 형식을 PDF 페이지로 통일 | 분석, 파싱, 위치 표시, 화면을 한 가지 방식으로 처리 | 페이지 개념이 없는 형식(긴 HTML 등)을 주로 다룰 때 |
| 규칙이 먼저 분류하고 VLM은 애매한 페이지만 | 속도와 부하, 근거 설명 가능성 | VLM이 충분히 빠르고 규칙 정확도가 낮을 때 |
| 파싱 준비는 프로세스 풀 | PyMuPDF가 GIL을 잡음(측정으로 확인) | 메모리가 부족하면 `parse.workers`를 줄인다 |
| Redis/arq 대신 서버 안 asyncio 작업 | 서버 1대면 충분하고 반입할 구성요소가 적음 | 여러 인스턴스, 재시작 후 이어서 실행이 필요할 때 |
| SQLite + 내장 Qdrant 기본 | 설치 없이 동작 | 동시 사용자 증가, 이중화 |
| BM25(한글 bigram) + RRF, sparse 벡터 안 씀 | 형태소 분석기와 모델 의존성 없이 오프라인 환경에서 동작 | bge-m3 sparse 출력을 vLLM에서 쓸 수 있게 되면 |
| PCA(numpy), UMAP 안 씀 | 반입할 의존성을 줄임 | 시각화 품질이 중요해질 때 |
| xlsx는 기본 자체 렌더링 | LibreOffice는 넓은 시트를 페이지마다 잘라 표가 깨짐 | — |
| 재실행 시 이전 run의 벡터 삭제 | 문서당 최신 인덱스 하나만 검색되게 함 | run끼리 비교 검색이 필요할 때 (run별 collection) |

---

## 9. 개발 중 겪은 함정

- **PyMuPDF와 GIL**: 스레드로 페이지를 렌더링하면 실제로는 순차 실행된다. 프로세스를 써야 한다.
- **PyMuPDF는 같은 이미지 스트림을 한 번만 저장한다**: 같은 이미지를 반복 삽입한 벤치마크 PDF가 150MB가 아니라 2.4MB였다. 측정 도구의 결과도 확인해야 한다.
- **`insert_textbox`는 넘치면 아무것도 쓰지 않는다**(반환값 < 0). 합성 문서를 만들 때 반환값을 확인한다.
- **MuPDF는 제목 줄을 바로 위 문단 블록에 붙인다**: `extract_text_elements`가 글자 크기 전환 지점에서 블록을 나눈다.
- **SQLite는 timezone을 저장하지 않는다**: `to_dict`에서 UTC로 붙인다. 화면 캡처에서 9시간 차이로 발견했다.
- **내장 Qdrant는 경로당 client 하나만 허용**한다. 항상 `vectorstore.client()`를 쓴다.
- **저장 위치 설정은 재시작해야 적용된다**: DB engine과 Qdrant client를 import 시점에 만든다. 설정 파일(`RAG_SETTINGS_FILE`)은 환경 변수와 `.env`보다 우선순위가 낮다. 그래서 `RAG_DATA_DIR`을 환경 변수로 주면 화면에서는 잠긴다.
- **파일 경로는 데이터 폴더 기준 상대 경로로 저장한다**(`settings.stored_path` / `settings.resolve`). 새 코드에서 `Document.path`나 `pdf_path`를 읽을 때 `Path(...)`로 바로 열지 말고 `settings.resolve()`를 거친다.
- **`pymupdf.css_for_pymupdf_font`는 `pymupdf-fonts` 패키지가 필요**하다. 그래서 내장 폰트 버퍼(`pymupdf.Font("korea").buffer`)를 archive에 직접 넣는다.
- **asyncio Semaphore는 이벤트 루프에 묶인다**: TestClient는 테스트마다 새 루프를 쓰므로 VLM semaphore를 루프별로 만든다.
- **Windows bash heredoc**: Python 코드 안의 `\n`, 바이트 이스케이프, 한글이 깨질 수 있다. 코드 수정은 편집 도구를 쓴다.
- **Windows에서 서버를 강제 종료하면 exit 255**가 보인다. 정상이다.
- **mock 분류기는 항상 `diagram`이라고 답한다**: mock VLM으로 띄운 데모 화면의 "relabel → diagram" 결정은 mock 때문이다.
- **임베딩 화면의 점 겹침**: 비슷한 청크(dev-hash)는 같은 좌표에 모인다. 범례의 개수로 확인한다.

---

## 10. 자주 쓰는 명령

```bash
cd backend && ../.venv/Scripts/python -m pytest -q                         # 테스트
../.venv/Scripts/python -m uvicorn app.main:app --port 8000                # 서버
cd frontend && npm run dev                                                 # UI 개발 (proxy :8000)
python scripts/mock_vllm.py --port 8001 --latency 0.3                      # mock 모델 서버
python scripts/bench_large.py --mb 207 --pages 300 --vlm-url http://127.0.0.1:8001/v1
python scripts/make_eval_set.py
python scripts/eval_profile.py --labels evals/synthetic/profile_labels.json --sweep --out evals/reports/p.md
python scripts/eval_retrieval.py --dataset evals/synthetic/retrieval.json --models config/models.yaml --out evals/reports/r.md
RAG_MODELS_FILE=other.yaml RAG_DATA_DIR=/tmp/x ...                         # 설정과 데이터 분리 실행
```

## 11. 이 문서 갱신 규칙

- 마일스톤이나 큰 기능이 끝나면 1절 표와 6절 목록을 갱신한다.
- 성능이나 품질을 측정하면 7절에 한 줄 추가한다. 조건을 반드시 적는다.
- 새로 겪은 함정은 9절에 추가한다.
- 검증 수준이 바뀌면(실제 모델 연결 등) 1절 "검증 수준" 표를 가장 먼저 고친다.
