# 진행 상황

2026-10-08 기준이다. IngestLens v1.0.0(AGPL-3.0)을 MIT 라이선스로 배포하기 위한 작업을 정리한다. 전체 상태와 백로그는 `docs/HANDOFF.md`, 라이선스 근거는 `NOTICE.md`에 있다.

## 1. 요약

| 항목 | 상태 |
|---|---|
| PyMuPDF 제거, MIT 전환 | 완료 (2026-10-04). 커밋 `bf70559` |
| GitHub 저장소 연결, push | 완료. https://github.com/kisubkim/IngestLens-MIT (`main`) |
| 원본 IngestLens의 새 기능 반영 | 완료. 2026-10-05에 `19aab24`까지, 2026-10-08에 main `ffb962c`까지. Docker·Singularity 이미지 관련 부분은 제외 |
| 실제 문서로 PDF 처리 결과 비교 | 실제 공개 문서 10종과 합성 VLM 세트를 실제 모델(`qwen2.5vl:7b`)로 비교함(2절) |

## 2. 완료한 것

### 2-1. PyMuPDF 교체 (2026-10-04)

PyMuPDF는 AGPL-3.0(또는 Artifex 상업 라이선스)이라 MIT로 배포하려면 쓸 수 없다. 하던 일을 다음 라이브러리로 나눴다.

| 하는 일 | 지금 쓰는 것 | 라이선스 | 코드 |
|---|---|---|---|
| 텍스트 블록, 줄, 글자 크기, 이미지, 벡터 경로, 괘선 표 읽기 | pdfplumber / pdfminer.six | MIT | `backend/app/tools/pdf.py` |
| 페이지 이미지, 크롭, 페이지 수, 암호 확인 | pypdfium2 | Apache-2.0 / BSD-3-Clause | `backend/app/tools/pdf.py` |
| 이미지 → PDF, Office 자체 렌더링, 테스트·합성 문서 | ReportLab | BSD | `backend/app/tools/pdfgen.py`, `office_native.py` |

- **한글 폰트**: PyMuPDF 내장 폰트 대신 `RAG_CJK_FONT`, 시스템 TrueType 폰트(맑은 고딕, 나눔고딕 등), 포함하지 않는 CID 폰트 순서로 고른다. intake가 "office font" 결정으로 기록한다.
- **파서 id**: `pymupdf_text`/`pymupdf_tables` → `native_text`/`native_tables`.
- **그림 클러스터**: PyMuPDF `cluster_drawings`와 같은 동작(3pt 이내 경로 묶기, 폭·높이 3pt 이하 제거)을 직접 구현했다(`tools/figures.py`).
- **라이선스 문서**: `LICENSE`를 MIT 전문으로 바꿨다. `NOTICE.md`, `README.md`, `docs/HANDOFF.md`를 갱신했다.
- 검증: 같은 합성 PDF에서 PyMuPDF와 페이지 라벨 전부 일치, 합성 세트 분류 100%, 150MB 벤치마크(VLM 사용 27.2s, 없음 8.3s), 6개 형식 수집, 설치 패키지 84개 라이선스 확인(GPL/AGPL/LGPL 없음).

### 2-2. 원본 IngestLens의 새 기능 반영 (2026-10-05)

원본 `3ce001b..19aab24`(커밋 6개, 80개 파일)를 3-way로 적용하고 MIT 버전에 맞게 고쳤다.

들어온 기능:
- **VLM 평가**: `scripts/eval_vlm.py`, `make_vlm_set.py`, `make_sample_set.py`, `tools/vlm_checks.py`, `api/evals.py`, "VLM 평가 비교" 화면(`/#evals`), 합성 세트(`evals/vlm/`), 실제 공개 문서 10종(`evals/samples/`, 출처 `SOURCES.md`), 원본에서 잰 결과 5개(`evals/results/vlm/`).
- **첫 화면 현황판**(`/api/overview`), **백엔드 상태 화면**(`/api/status`, `/#status`), **문서 삭제와 전체 삭제**(`tools/purge.py`), 파싱 리포트의 요소 통계(`/api/runs/{id}/element-stats`).
- **VLM 답 잘림 재시도**: `vlm.max_tokens_retry`로 한 번 더 묻고 `vlm_truncated_retry` 결정으로 남긴다. 캡션 규칙에 `[그림 1]`, `<표 1>` 같은 대괄호 형식 추가.
- **모델 서버**: 임베딩과 reranker를 GPU 프로세스 하나로 띄우는 vLLM 호환 서버(`deploy/model-server/server.py`, `deploy/model-server.sh`). 오프라인 설치 안내(`deploy/README.md`), 임베딩 모델 후보 문서(`docs/EMBEDDING_MODELS.md`).
- **설정**: `RAG_ADMIN_HOSTS`(이 PC로 볼 주소/대역), `RAG_DATA_DIR_HINT`, `RAG_EVALS_DIR`.

뺀 것 (Docker 이미지 관련): `docker-compose.yml`, `docker/app.Dockerfile`, `docker/model-server/Dockerfile`, `docker/certs/`, `.dockerignore`, `config/models.docker*.yaml`, `deploy/docker-compose.yml`, `deploy/install.sh`, `deploy/.env.example`, `scripts/build_offline_bundle.py`, `start_test.*`/`stop_test.*`.

MIT 버전에 맞게 고친 것:
- `make_vlm_set.py`, `make_sample_set.py`, `test_purge.py`를 PyMuPDF 대신 `PdfWriter`/pypdfium2로 바꿨다. `PdfWriter`에 채운 사각형과 꺾은선을 더했다.
- `eval_vlm.py`의 `dataset_version`을 렌더한 픽셀 대신 PDF 파일 바이트로 계산한다(렌더러가 바뀌어도 값이 같다).
- 모델 서버를 `docker/model-server/`에서 `deploy/model-server/`로 옮겼다. 앱 설치는 Docker 이미지 대신 Python wheel(`deploy/README.md`).
- 개발 PC용 실제 모델 설정 `config/models.ollama.yaml`(PC의 Ollama + 모델 서버)을 새로 만들었다(원본의 Docker 스택 대신).
- `NOTICE.md`(평가 PDF 라이선스 예외, 모델 서버 의존성), `README.md`, `docs/HANDOFF.md`, `evals/README.md`, `evals/samples/SOURCES.md`의 AGPL·Docker 문구를 고쳤다. 상태 화면의 `docker compose` 안내 문구도 바꿨다.
- pdfminer의 폰트 경고(`Could not get FontBBox ...`)가 실제 문서에서 로그를 덮어서 ERROR 이상만 남긴다.

### 2-3. 검증 (2026-10-05)

- 백엔드 테스트 64개 통과(기존 46 + 원본에서 온 16 + 이번에 더한 회귀 테스트 2). 화면 빌드(`npm run build`, tsc 포함) 통과.
- 8010 포트로 앱을 띄워 상태 화면 API가 실제 모델 3개(임베딩, VLM, reranker)를 "정상"으로 잡는 것, 평가 결과 5개 목록, 첫 화면 현황, 실제 `bge-m3`로 처리한 docx 문서의 삭제(벡터까지 0개)를 확인했다.
- **갈린 체크의 원인과 보정**: 좌우 바깥 세로선이 없는 "열린 표"에서 pdfplumber가 행 이름 열과 마지막 열(`168,671`)을 버렸다(PyMuPDF는 잡았다). 가로 규칙선 양 끝에 가상 테두리를 더하는 보정(`tools/pdf.py` `_open_side_edges`)을 넣어 그 표가 7열 → 9열로 돌아온 것을 확인했고 회귀 테스트를 더했다(`test_open_sided_table_keeps_outer_columns`). 평가 PDF 12개 전체에서 이 보정으로 바뀐 표는 국가데이터처 보도자료의 열린 표뿐이었다. 같은 페이지의 표 2는 VLM 재추출이 빈 열만 반복하는 답을 냈다(원본 실행에서는 정상). 크롭이 달라서인지 모델이 우연히 실패했는지는 다시 돌려 봐야 안다.
- **표 2의 VLM 재추출 실패**: 같은 크롭을 직접 보내 보니 넓은 크롭(보정 후)은 2번 모두, 좁은 크롭(보정 전)도 2번 중 1번 머리글 반복으로 `max_tokens`에서 잘렸다. 모델이 이 표에서 원래 흔들린다. 원본의 3b 실행은 재추출이 오류로 끝나 원래 표를 지켜서 통과했다. 그래서 **재시도 후에도 잘린 표 답은 버리고 원래 표를 유지**하게 바꿨다(`vlm_table_truncated` 결정, `test_truncated_table_reextraction_keeps_native_table`). 원래 표에는 모든 셀 글자가 들어 있다(행이 한 셀로 뭉칠 뿐).
- 두 보정 뒤 다시 잰 결과가 위 표의 92%(38/43)다(`evals/results/vlm/20261004-181351_ollama-qwen2.5vl-7b.json`). 중간에 원본 쪽 Docker Desktop이 한동안 응답을 멈춰 재측정이 늦어졌다.
- **실제 모델로 원본과 비교**: 원본이 기록한 결과와 같은 입력 PDF, 같은 모델 구성(Ollama `qwen2.5vl:7b` + `bge-m3`, reranker `bge-reranker-v2-m3` CPU, RTX 5070 Ti)으로 `eval_vlm.py`를 돌렸다. 달라진 것은 PDF 처리 스택뿐이다.

| 세트 | 원본 (PyMuPDF) | 이 버전 | 차이 |
|---|---|---|---|
| 합성 5페이지 (`evals/vlm/`) | 92% (17/19), OCR CER 0 | 92% (17/19), OCR CER 0 | 같음. 실패 2개(그림 설명이 영어)도 같다 |
| 실제 공개 문서 10종 (`evals/samples/`) | 92% (38/43) | 처음 91% (37/43) → 보정 2개 후 **92% (38/43)** | 보정 후 17페이지 모두 체크 결과가 원본과 같다 |

### 2-4. 원본 main 추가 반영 (2026-10-08)

원본 main에 생긴 커밋 4개(`56afa46`, `6030df0`, `f5ba5cc`, `ffb962c`)를 확인하고, 원본 main과 파일 단위로 다시 대조했다.

들어온 것:
- **Open WebUI 쪽 번호 수정**: `/api/openwebui/process`의 metadata `page`를 0부터 보낸다(Open WebUI가 +1 해서 보여준다). `page_label`, `pages`는 1부터.
- **문서 하나 삭제의 관리자 키**: `RAG_API_KEY`가 설정된 서버에서 문서 화면의 "문서 삭제"가 키 없이 요청해 401로 실패하던 문제. 키를 묻고 그 탭에서 기억한다(화면 3개 파일).
- **Open WebUI 연동 가이드** `deploy/OPENWEBUI.md`와, Open WebUI가 임베딩·rerank 모델 서버를 함께 쓰는 설정(`deploy/README.md` 8절). IngestLens를 Docker·Singularity로 띄운다는 부분은 이 저장소의 실행 방법(uvicorn, `deploy/model-server.sh`)으로 바꿨다. Open WebUI 자체를 Docker로 띄우는 예시는 Open WebUI 쪽 이야기라 그대로 뒀다.
- NOTICE(Qwen2.5-VL 3B 비상업 조건, Ollama MIT, 별도 프로그램 안내), README, HANDOFF(마일스톤, 검증 수준, 백로그, 측정, 함정), EMBEDDING_MODELS.

뺀 것: Singularity/Apptainer 이미지(`deploy/singularity.sh`, `singularity.env.example`, `docker/model-server/release.Dockerfile`, `build_offline_bundle.py --singularity`), Docker Desktop 약관과 배포 이미지 구성 요소(NOTICE의 해당 부분). Docker처럼 컨테이너 이미지를 만드는 부분이라 같은 기준으로 뺐다.

원본 main과 대조한 결과, 남은 차이는 모두 의도한 것이다: PDF 라이브러리 교체(코드, 테스트, 생성 스크립트), Docker·Singularity 제외, 모델 서버 위치(`deploy/model-server/`), MIT 문서, 이 저장소에서 더한 것(열린 표 보정, 잘린 표 답 처리, `config/models.ollama.yaml`, 평가 결과 2개). 원본 작업 폴더에 커밋되지 않은 파일(`api/chunks.py` 등)은 main에 없어서 넣지 않았다.

검증: 테스트 64개 통과, 화면 빌드 통과.

### 2-5. 원본 `webui` 브랜치 반영 (2026-10-08)

원본 IngestLens의 `webui` 브랜치(main `ffb962c` 위 커밋 4개, 끝 `d525d4a`)를 이 저장소의 main에 넣었다.

- **청크 영역을 칠한 쪽 이미지 API** `GET /api/chunks/{id}/preview.png`(`page`, `dpi`, `highlight=false`). 문서를 지우면 캐시도 함께 지워진다. 원본은 PyMuPDF로 페이지에 사각형을 그려 렌더했는데, 여기서는 PDFium으로 렌더한 이미지에 Pillow로 반투명 사각형을 칠한다(PDF는 바꾸지 않는다). 테스트도 Pillow 비교로 바꿨다.
- **Open WebUI 쪽 이미지 필터** `deploy/openwebui_page_images.py`: 답변 아래 썸네일 줄(누르면 펼치고 접음)과 출처 팝업에 그 쪽 이미지를 보여준다. 가이드는 `deploy/OPENWEBUI.md` 10절.
- 쪽 이미지 해상도 하한을 18 dpi로 낮췄다(썸네일용).
- HANDOFF(검증 수준, 폴더 지도, Open WebUI 필터 함정). 원본 PROGRESS는 가져오지 않았다.

검증: 테스트 65개 통과(청크 미리보기 테스트 포함), 칠한 이미지를 눈으로 확인. 실제 Open WebUI에 필터를 붙여 보는 것은 원본에서만 했다.

## 3. 다음에 할 일

1. **원본 IngestLens에도 "잘린 표 답은 원래 표 유지" 수정을 알린다**: 원본도 같은 약점이 있다(이번 원본 결과의 통과는 7b가 우연히 성공했거나 3b가 오류로 끝난 덕분이다).
2. **Linux 서버 확인**: 이 버전(새 PDF 라이브러리)은 Linux에서 돌려 본 적이 없다. 한글 TrueType 폰트(`fonts-nanum`) 설치, "office font" 결정이 `font_system`/`font_configured`인지, 프로세스 풀 동작.
3. **모델 서버 실제 운영 GPU 확인**: Exclusive_Process 모드에서 `./model-server.sh status`로 GPU 프로세스가 1개인지.
4. **원본 IngestLens와 계속 맞추기**: 원본에 기능이 더 생기면 같은 방식(3-way 적용 → PyMuPDF 사용처 교체 → Docker 이미지 부분 제외)으로 반영한다. 이번 반영 기준은 원본 `19aab24`다.
5. **필요하면 git 이력 정리**: 첫 커밋 `6b6c37b`에 AGPL 전문과 PyMuPDF 코드가 남아 있다. 지금도 문제는 없지만, 이력에서 빼고 싶으면 커밋을 합친다(force push 필요).

## 4. 막혔던 문제와 해결

| 문제 | 원인 | 해결 |
|---|---|---|
| 원본 diff를 적용했더니 평가 PDF 11개가 깨짐(118KB → 18KB, 내용이 텍스트) | Git for Windows 시스템 설정의 `diff.astextplain.textconv`가 `git diff`에서 PDF를 텍스트로 바꿔 패치에 넣었다 | 원본 blob에서 그대로 복원하고 해시를 대조했다. `.gitattributes`에 `*.pdf binary`를 넣어 다시 생기지 않게 했다 |
| bash heredoc으로 쓴 Python에서 `"\n".join`이 실제 줄바꿈으로 바뀜 | Windows bash heredoc 함정(CLAUDE.md에 적혀 있던 것) | 편집 도구로 고쳤다. 코드 수정은 편집 도구를 쓴다 |
| 원본의 `.sh` 파일이 CRLF로 풀림 | 패치 적용이 작업 사본에 CRLF로 썼다 | LF로 바꿨다. `.gitattributes`가 커밋 시 LF로 맞춘다 |
| 렌더러가 바뀌면 VLM 평가 세트 버전이 달라짐 | 원본은 렌더한 픽셀로 `dataset_version`을 계산했다 | 파일 바이트로 계산하게 바꿨다. 원본 결과 5개와는 버전이 달라 화면이 경고한다(입력 PDF와 기대값은 같다) |
| 벤치마크에서 `--vlm-url`을 줘도 VLM 호출이 0회 (2026-10-04) | `make_pdf`가 `app.tools.pdfgen`을 import하면서 설정이 환경 변수 설정 전에 읽혔다 | 환경 변수 설정 뒤에 PDF를 만들도록 순서를 바꿨다 |
| 벤치마크 PDF가 150MB가 아니라 102MB (2026-10-04) | Pillow JPEG가 PyMuPDF보다 픽셀당 바이트가 적다 | 크기 상수를 2.3 → 1.57로 다시 맞췄다 |
| pdfplumber가 다이어그램 상자를 1×1 표로 잡음 | "lines" 전략은 사각형 하나도 표로 본다 | 2행 2열 미만 표는 버린다(`Page.tables()`) |
| 회전 결과 세로로 놓인 글이 한 글자씩 줄로 나뉨 | pdfminer `detect_vertical`이 꺼져 있다 | 미해결. 드문 경우라 HANDOFF §9에 적어 두었다 |
| Noto Sans CJK 같은 `.otf` 폰트 | ReportLab은 TrueType(`glyf`) 폰트만 넣을 수 있다 | 등록에 실패하면 다음 후보로 넘어가고 실패 목록을 결정에 남긴다 |
| 개발 서버 포트 | 8000번을 다른 프로그램이 쓰고 있었다 | 확인용으로만 앱 8010, mock vLLM 8011을 썼다. 설정 파일은 바꾸지 않았다 |

## 5. 로컬 환경 메모

- `CLAUDE.md`와 한글 번역본 `CLAUDE_KR.md`는 `.git/info/exclude`에 넣어 커밋하지 않는다.
- venv(`.venv`)에는 PyMuPDF가 없다. `pip install -r backend/requirements-dev.txt`로 새 의존성이 설치된다.
- 원본 IngestLens는 `../IngestLens`에 있다. 이 저장소에 `upstream-local/main`으로 가져와(fetch) 비교했다.
