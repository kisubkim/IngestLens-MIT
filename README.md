# IngestLens

Explainable RAG document ingestion: parse, chunk, embed — with the evidence behind every decision.

웹에서 문서를 선택하면 여러 agent가 다음 순서로 처리한다: 형식 판별 → 콘텐츠 분석 → 전략 결정 → 파싱 → 청킹 → 임베딩.
각 단계의 진행 상황과 결정 근거를 웹에서 실시간으로 볼 수 있다. 외부 API 없이 직접 띄운 vLLM(OpenAI 호환) endpoint만 사용하므로, 인터넷이 없는 환경에서도 동작한다.

현재 상태: M1–M6 구현 완료. **실제 모델은 아직 연결하지 않았다.** VLM은 mock, 임베딩은 dev-hash로만 검증했다.

- 계획: `docs/PLAN.md`
- 이어서 작업할 때 필요한 내용(상태, 반입 절차, 백로그, 함정): **`docs/HANDOFF.md`**
- 평가와 튜닝: `evals/README.md`
- 라이선스: AGPL-3.0 (`LICENSE`). 의존성과 모델의 라이선스는 `NOTICE.md`

## 실행 (개발)

```bash
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements-dev.txt
cd frontend && npm install && npm run build && cd ..

cd backend
../.venv/Scripts/python -m uvicorn app.main:app --port 8000   # http://localhost:8000 (UI 포함)
```

UI 개발: `cd frontend && npm run dev`. `/api`는 `127.0.0.1:8000`으로 proxy된다.

## 설정

- `config/models.yaml`: vLLM endpoint를 설정한다. `base_url`이 비어 있으면 다음처럼 동작한다.
  - VLM: native 파서로 fallback한다.
  - 임베딩: dev-hash embedder를 쓴다. 검색 품질은 의미가 없다.
  - reranker(선택): 검색 화면의 rerank 옵션이 비활성화된다. vLLM `/v1/rerank`를 사용한다.
- `config/strategy_rules.yaml`: 페이지 분류 규칙, 파서 매핑, 청킹 파라미터, 파싱 병렬도(`parse.workers`, `parse.windows_in_flight`), 그림/캡션/표 재추출 기준.
- 환경 변수(`RAG_` prefix, `.env` 파일도 가능):

| 변수 | 기본값 | 설명 |
|---|---|---|
| `RAG_DATA_DIR` | 저장소의 `data/` | 업로드, 변환 결과, 페이지 이미지, SQLite, 내장 Qdrant 저장 위치 |
| `RAG_DB_URL` | SQLite | 예: `postgresql+psycopg://...` |
| `RAG_QDRANT_URL` | 내장 모드 | 예: `http://qdrant:6333` |
| `RAG_SOFFICE_PATH` | PATH 검색 | Office 문서를 PDF로 변환할 LibreOffice 경로. 없으면 docx/pptx/xlsx는 자체 렌더링한다 |
| `RAG_MODELS_FILE` | `config/models.yaml` | 다른 모델 설정 파일을 쓸 때 (예: mock 서버용) |
| `RAG_API_KEY` | 없음 | 수집 API(`/api/ingest`, `/api/openwebui/process`)와 저장 위치 변경의 Bearer 키. 비어 있으면 수집 API는 인증하지 않고, 저장 위치 변경은 서버 PC에서 접속했을 때만 허용한다. 그 밖의 화면용 API에는 적용하지 않는다 |
| `RAG_SETTINGS_FILE` | `config/settings.local.yaml` | 저장 위치 설정 화면이 쓰는 파일. git에 올라가지 않는다 |
| `RAG_INGEST_WAIT_SECONDS` | `3600` | Open WebUI 로더가 실행 완료를 기다리는 최대 시간. 넘으면 504를 돌려준다 |

### 저장 위치

모든 데이터는 데이터 폴더(`RAG_DATA_DIR`) 아래에 저장된다.

| 경로 | 내용 |
|---|---|
| `uploads/{문서id}/` | 올린 원본 파일 |
| `converted/{문서id}/` | Office·이미지를 변환한 PDF |
| `pages/{문서id}/{페이지}_{dpi}.png` | 페이지 이미지 캐시. 화면에서 처음 볼 때 만든다 |
| `rag.db` | SQLite DB(문서, 실행, 결정 근거, 요소, 청크). `RAG_DB_URL`을 설정하면 그 DB를 쓴다 |
| `qdrant/` | 내장 Qdrant(임베딩 벡터). `RAG_QDRANT_URL`을 설정하면 그 서버를 쓴다 |

화면 왼쪽 아래 **저장 위치 설정**에서 항목별 위치와 용량을 보고, 데이터 폴더, DB 주소, Qdrant 주소를 바꿀 수 있다.
- 바꾼 값은 `RAG_SETTINGS_FILE`에 저장되고 **서버를 재시작해야 적용된다.** 같은 항목을 환경 변수나 `.env`로 설정했다면 그쪽이 우선하며, 화면에서는 바꿀 수 없다.
- 기존 데이터는 자동으로 옮기지 않는다. DB에는 파일 경로가 데이터 폴더 기준 상대 경로로 저장되므로, 서버를 멈춘 뒤 데이터 폴더를 통째로 새 위치에 복사하면 그대로 이어서 쓸 수 있다. 이전 버전이 저장한 절대 경로는 서버가 시작할 때 상대 경로로 바뀐다.

## 테스트

```bash
cd backend && ../.venv/Scripts/python -m pytest -q
```

## 지원 형식

| 형식 | 처리 |
|---|---|
| PDF | 그대로 처리 |
| 이미지 (png/jpg/tif) | 1페이지 PDF로 감싸서 처리 |
| docx / pptx | LibreOffice가 있으면 LibreOffice로 PDF 변환하고, 없으면 자체 렌더링(python-docx/pptx → HTML → PDF). 두 경우 모두 원본에서 헤딩, 슬라이드 제목, 발표자 노트, PPT 차트 데이터를 추가로 추출한다 |
| xlsx | 기본은 자체 렌더링. 시트를 24행 단위 표로 나누고 헤더를 반복한다 (`office.xlsx`) |
| doc / ppt / hwp 등 | LibreOffice 필요 |

## 검색 방식

검색 화면(`POST /api/search`)은 한 run의 청크를 대상으로 세 가지 방식을 지원한다.

- `dense`: Qdrant cosine 검색
- `lexical`: BM25. 한글은 음절 bigram으로 색인하므로 형태소 분석기가 필요 없다.
- `hybrid`: RRF(k=60) 융합. dense와 BM25 가중치를 조절할 수 있다.

reranker가 설정되어 있으면 후보를 다시 정렬한다. 결과마다 단계별 점수와 순위를 함께 반환한다.

## HTTP 수집 API (다른 시스템 연동)

화면 버튼 없이 HTTP로 파일을 보내면 바로 파이프라인이 실행된다. 실행은 화면에서 시작한 것과 같은 줄에 서서 들어온 순서대로 하나씩 진행된다. `RAG_API_KEY`를 설정했으면 `Authorization: Bearer <키>` 헤더가 필요하다.

- `POST /api/ingest`: multipart `files`(여러 개 가능). 저장 후 실행을 등록하고 바로 응답한다. 진행 상황은 `GET /api/runs/{run.id}`로 확인한다. 같은 파일(sha256)이 이미 있고 마지막 실행이 성공이나 진행 중이면 다시 실행하지 않고 그 실행을 돌려준다.

  ```bash
  curl -H "Authorization: Bearer $KEY" -F files=@a.pdf -F files=@b.docx http://localhost:8000/api/ingest
  ```

- `PUT /api/openwebui/process`: Open WebUI의 External 문서 로더 규약. 본문은 파일 바이트, 파일 이름은 `X-Filename` 헤더(URL 인코딩)로 받는다. 실행이 끝날 때까지 기다렸다가 청크를 `[{page_content, metadata}]`로 돌려준다. metadata에는 `source`, `document_id`, `run_id`, `chunk_id`, `page`(1부터), `pages`, `section`, `element_types`가 들어간다. 실행이 실패하면 502, 기다리는 시간이 `RAG_INGEST_WAIT_SECONDS`를 넘으면 504를 돌려준다.

### Open WebUI 설정

관리자 설정 → 문서 → 콘텐츠 추출 엔진을 `External`로 바꾸고, URL에 `http://<이 서버>:8000/api/openwebui`, API 키에 `RAG_API_KEY` 값을 넣는다. 환경 변수로는 `CONTENT_EXTRACTION_ENGINE=external`, `EXTERNAL_DOCUMENT_LOADER_URL`, `EXTERNAL_DOCUMENT_LOADER_API_KEY`다. 그러면 Open WebUI에 파일을 추가할 때마다 이 서버가 파일을 받아 파이프라인을 실행하고, Open WebUI는 돌려받은 청크를 자기 지식 베이스에 넣는다. 처리 과정과 결정 근거는 이 서버 화면에서 볼 수 있다.

## GPU 없이 VLM 경로 확인 (mock vLLM)

```bash
.venv/Scripts/python scripts/mock_vllm.py --port 8001 --latency 0.3
```

`models.yaml`의 `vlm.base_url`을 `http://127.0.0.1:8001/v1`로 설정한다. 원본을 건드리지 않으려면 복사본을 만들고 `RAG_MODELS_FILE`로 지정한다.
mock 서버는 prompt 규약(OCR, 그림 `TYPE:` 첫 줄, 표, 분류)에 맞는 고정 답을 돌려준다. `/v1/embeddings`, `/v1/rerank`, `/tokenize`도 제공한다.

## 대용량 벤치마크

```bash
.venv/Scripts/pip install -r backend/requirements-dev.txt
.venv/Scripts/python scripts/bench_large.py --mb 207 --pages 300 --vlm-url http://127.0.0.1:8001/v1
```

`--mb`는 생성할 이미지 총량이다. 207을 주면 약 150MB PDF가 만들어진다. 출력은 단계별 시간, VLM 호출 통계, 최대 메모리(worker 포함)다.

참고 측정값 (12코어 PC, mock VLM latency 0.3s, 동시 4개, `parse.workers: 4`). 150MB, 300페이지(텍스트 100, 텍스트+그림 100, 스캔 100)를 처리했다.

| 조건 | 전체 | 파싱 | 최대 메모리 |
|---|---|---|---|
| VLM 사용 (호출 200회) | 28.9s | 20.9s | 1.1GB |
| VLM 없음 | 5.6s | 1.6s | 0.6GB |

실제 VLM에서는 호출 1회의 latency가 전체 시간을 결정한다. 대략 `호출 수 × latency / max_concurrency`다.

## 평가 (M6)

```bash
.venv/Scripts/python scripts/make_eval_set.py          # 합성 평가 세트 생성 (evals/synthetic)
.venv/Scripts/python scripts/eval_profile.py --labels evals/synthetic/profile_labels.json --sweep
.venv/Scripts/python scripts/eval_retrieval.py --dataset evals/synthetic/retrieval.json
```

라벨 형식, 튜닝 순서, 현재 기준선은 `evals/README.md`에 있다.
