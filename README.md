# IngestLens

Explainable RAG document ingestion: parse, chunk, embed — with the evidence behind every decision.

웹에서 문서를 선택하면 여러 agent가 다음 순서로 처리한다: 형식 판별 → 콘텐츠 분석 → 전략 결정 → 파싱 → 청킹 → 임베딩.
각 단계의 진행 상황과 결정 근거를 웹에서 실시간으로 볼 수 있다. 외부 API 없이 직접 띄운 vLLM(OpenAI 호환) endpoint만 사용하므로, 인터넷이 없는 환경에서도 동작한다.

현재 상태: M1–M6 구현 완료. **실제 모델은 아직 연결하지 않았다.** VLM은 mock, 임베딩은 dev-hash로만 검증했다.

- 계획: `docs/PLAN.md`
- 이어서 작업할 때 필요한 내용(상태, 반입 절차, 백로그, 함정): **`docs/HANDOFF.md`**
- 평가와 튜닝: `evals/README.md`
- 라이선스: MIT (`LICENSE`). 의존성과 모델의 라이선스는 `NOTICE.md`. v1.0.0(AGPL-3.0)에서 쓰던 PyMuPDF를 pdfplumber/pdfminer.six, pypdfium2, ReportLab으로 바꿨다

## 실행 (개발)

```bash
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements-dev.txt
cd frontend && npm install && npm run build && cd ..

cd backend
../.venv/Scripts/python -m uvicorn app.main:app --port 8000   # http://localhost:8000 (UI 포함)
```

UI 개발: `cd frontend && npm run dev`. `/api`는 `127.0.0.1:8000`으로 proxy된다.

## 첫 화면 (임베딩 DB 현황)

문서를 고르지 않았을 때나 왼쪽 위 "IngestLens"를 누르면 보인다. 문서 수와 원본 용량, 페이지 수, 벡터와 청크 수(문서별 최신 실행), 임베딩 모델, 실행 결과, 데이터 폴더별 디스크 사용량, 최근 문서를 보여준다. 최근 문서를 누르면 그 문서가 열린다. API: `GET /api/overview`

## 문서 삭제

- **문서 하나:** 문서를 연 뒤 오른쪽 위 "문서 삭제". 올린 원본, 변환 PDF, 페이지 이미지, 모든 실행 기록, 파싱·청크 결과, 임베딩 벡터를 함께 지운다.
- **전체:** 저장 위치 설정 화면 아래 "데이터 비우기 → 전체 삭제". 확인을 위해 "전체 삭제"를 입력해야 한다.
- 실행 중이거나 대기 중인 문서는 지울 수 없다. 먼저 실행을 취소한다.
- 저장 위치 설정과 같이 서버가 돌아가는 PC에서만 지울 수 있다(`RAG_API_KEY`를 설정하면 그 키로 어디서나).
- API: `DELETE /api/documents/{id}`, `DELETE /api/documents?confirm=all`

## 백엔드 상태 확인

화면 왼쪽 아래에 백엔드 상태가 색으로 표시된다(초록 정상, 노랑 주의, 빨강 오류나 연결 안 됨). 15초마다 다시 확인하며, 누르면 `/#status`에서 항목별로 볼 수 있다.

- 확인 항목: API 서버, DB, 벡터 DB, 임베딩, VLM, reranker, LibreOffice, 실행 대기열
- 모델 서버는 `GET {base_url}/models`로 응답과 설정한 모델이 있는지 본다. models.yaml에 주소를 비운 항목은 "꺼짐"으로 표시하며, 파이프라인은 대체 방식으로 계속 동작한다.
- API: `GET /api/status` (결과는 5초 동안 재사용, `?refresh=true`면 바로 다시 확인)

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
| `RAG_CJK_FONT` | 시스템 검색 | 자체 렌더링(Office, 이미지)이 PDF에 넣을 한글 TrueType 폰트 경로. 비우면 맑은 고딕, 나눔고딕 등을 찾고, 없으면 포함하지 않는 CID 폰트를 쓴다 |
| `RAG_MODELS_FILE` | `config/models.yaml` | 다른 모델 설정 파일을 쓸 때 (예: mock 서버용) |
| `RAG_API_KEY` | 없음 | 수집 API(`/api/ingest`, `/api/openwebui/process`), 저장 위치 변경, 문서 삭제의 Bearer 키. 비어 있으면 수집 API는 인증하지 않고, 저장 위치 변경과 문서 삭제는 서버 PC에서 접속했을 때만 허용한다. 그 밖의 화면용 API에는 적용하지 않는다 |
| `RAG_ADMIN_HOSTS` | 없음 | "서버 PC에서 접속"으로 볼 추가 IP나 CIDR(쉼표로 구분). reverse proxy나 컨테이너 포트 공개 뒤에서 이 PC의 요청이 다른 주소로 들어올 때 쓴다 |
| `RAG_DATA_DIR_HINT` | 없음 | 데이터 폴더가 환경 변수로 잠겨 있을 때 설정 화면에 보여 줄 안내 문구 |
| `RAG_EVALS_DIR` | `evals/results` | VLM 평가 비교 화면이 읽는 결과 폴더 |
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
| docx / pptx | LibreOffice가 있으면 LibreOffice로 PDF 변환하고, 없으면 자체 렌더링(python-docx/pptx → ReportLab → PDF). 두 경우 모두 원본에서 헤딩, 슬라이드 제목, 발표자 노트, PPT 차트 데이터를 추가로 추출한다 |
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

## 오프라인 서버에 배포

인터넷 없는 리눅스 서버에 앱은 Python wheel로 설치하고, 모델은 서버에 이미 있는 vLLM과 모델 서버를 쓴다. Docker는 필요 없다.

- 앱: 인터넷 되는 PC에서 wheel과 빌드된 화면(`frontend/dist`)을 준비해 반입한다. 순서는 `docs/HANDOFF.md` 3-2절에 있다.
- VLM: 이미 운영 중인 vLLM을 쓴다.
- 임베딩과 reranker: **모델 서버**(`deploy/model-server.sh start`)로 띄운다. GPU 1장에 프로세스 하나로 두 모델을 함께 올리며, root 권한 없이 vLLM의 Python 환경에서 실행한다.
- 모델 받기, `models.yaml` 설정, 확인, 업데이트, 백업 순서는 `deploy/README.md`에 있다.

## 로컬 PC에서 실제 모델로 실행

NVIDIA GPU가 있는 PC에서 Ollama(VLM `qwen2.5vl:7b`, 임베딩 `bge-m3`)와 모델 서버(reranker `BAAI/bge-reranker-v2-m3`, CPU)를 띄우고 앱을 연결한다. 모델은 약 9.5GB이고 처음 받을 때 인터넷이 필요하다.

```bash
ollama pull qwen2.5vl:7b && ollama pull bge-m3
.venv/Scripts/pip install torch transformers          # 모델 서버용. 앱 의존성과 따로 둬도 된다
.venv/Scripts/python deploy/model-server/server.py --rerank-model BAAI/bge-reranker-v2-m3 --device cpu --port 8090

cd backend
RAG_MODELS_FILE=../config/models.ollama.yaml ../.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

- `config/models.ollama.yaml`은 Ollama 기본 포트(11434)와 모델 서버(8090)를 가리킨다. 포트가 다르면 복사본(`*.local.yaml`)을 만들어 고친다.
- GPU 메모리가 적으면 `qwen2.5vl:3b`를 쓴다.
- Ollama에는 `/tokenize`가 없어서 토큰 비율은 기본값 2.5를 쓴다. 이 폴백은 결정 기록에 남는다.
- 실제 배포 대상은 vLLM이다. 이 구성은 로컬 검증용이다.

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

참고 측정값 (12코어 PC, mock VLM latency 0.3s, 동시 4개, `parse.workers: 4`, 2026-10-04, pdfplumber/pypdfium2). 149MB, 300페이지(텍스트 100, 텍스트+그림 100, 스캔 100)를 처리했다.

| 조건 | 전체 | 파싱 | 최대 메모리 |
|---|---|---|---|
| VLM 사용 (호출 200회) | 27.2s | 18.0s | 0.8GB |
| VLM 없음 | 8.3s | 1.9s | 0.75GB |

실제 VLM에서는 호출 1회의 latency가 전체 시간을 결정한다. 대략 `호출 수 × latency / max_concurrency`다.

## 평가 (M6)

```bash
.venv/Scripts/python scripts/make_eval_set.py          # 합성 평가 세트 생성 (evals/synthetic)
.venv/Scripts/python scripts/eval_profile.py --labels evals/synthetic/profile_labels.json --sweep
.venv/Scripts/python scripts/eval_retrieval.py --dataset evals/synthetic/retrieval.json
.venv/Scripts/python scripts/eval_vlm.py --models <models.yaml> --name "<모델 이름>"   # VLM 품질, 결과는 evals/results/vlm/
.venv/Scripts/python scripts/eval_vlm.py --cases evals/samples/cases.json --models <models.yaml> --name "<모델 이름>"   # 실제 공개 문서 10종
```

VL 모델끼리의 결과는 앱 왼쪽 아래 **"VLM 평가 비교"**(`/#evals`)에서 나란히 비교한다. 라벨 형식, 평가 항목, 튜닝 순서, 현재 기준선은 `evals/README.md`에 있다.
