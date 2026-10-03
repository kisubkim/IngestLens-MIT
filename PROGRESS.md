# 진행 상황

2026-10-04 기준이다. IngestLens v1.0.0(AGPL-3.0)을 MIT 라이선스로 배포하기 위한 작업을 정리한다. 전체 상태와 백로그는 `docs/HANDOFF.md`, 라이선스 근거는 `NOTICE.md`에 있다.

## 1. 요약

| 항목 | 상태 |
|---|---|
| PyMuPDF 제거, MIT 전환 | 완료. 커밋 `bf70559` |
| GitHub 저장소 연결, push | 완료. https://github.com/kisubkim/IngestLens-MIT (`main`) |
| 원본 IngestLens의 새 기능 반영 | **대기**. 원본 폴더에서 다른 세션이 작업 중이라 끝난 뒤 반영한다 |
| 실제 문서로 PDF 처리 결과 비교 | 안 함 |

## 2. 완료한 것

### PyMuPDF 교체

PyMuPDF는 AGPL-3.0(또는 Artifex 상업 라이선스)이라 MIT로 배포하려면 쓸 수 없다. 하던 일을 다음 라이브러리로 나눴다.

| 하는 일 | 지금 쓰는 것 | 라이선스 | 코드 |
|---|---|---|---|
| 텍스트 블록, 줄, 글자 크기, 이미지, 벡터 경로, 괘선 표 읽기 | pdfplumber / pdfminer.six | MIT | `backend/app/tools/pdf.py` |
| 페이지 이미지, 크롭, 페이지 수, 암호 확인 | pypdfium2 | Apache-2.0 / BSD-3-Clause | `backend/app/tools/pdf.py` |
| 이미지 → PDF, Office 자체 렌더링, 테스트·합성 문서 | ReportLab | BSD | `backend/app/tools/pdfgen.py`, `office_native.py` |

- **한글 폰트**: PyMuPDF 내장 폰트 대신 `RAG_CJK_FONT`, 시스템 TrueType 폰트(맑은 고딕, 나눔고딕 등), 포함하지 않는 CID 폰트 순서로 고른다. intake가 "office font" 결정으로 기록한다.
- **파서 id**: `pymupdf_text`/`pymupdf_tables` → `native_text`/`native_tables`.
- **그림 클러스터**: PyMuPDF `cluster_drawings`와 같은 동작(3pt 이내 경로 묶기, 폭·높이 3pt 이하 제거)을 직접 구현했다(`tools/figures.py`).
- **테스트, 스크립트**: conftest, office_fixtures, 테스트 5개, `bench_large.py`, `make_eval_set.py`, `eval_profile.py`를 새 라이브러리로 바꿨다. `evals/synthetic/manual.pdf`를 다시 만들었다.
- **라이선스 문서**: `LICENSE`를 MIT 전문으로 바꿨다. `NOTICE.md`(PDFium 바이너리 포함 의존성, 폰트, AGPL→MIT 경위), `README.md`, `docs/HANDOFF.md`를 갱신했다.

### 검증

- 테스트 46개 통과(PyMuPDF를 venv에서 지운 상태).
- 같은 합성 PDF를 PyMuPDF와 새 코드로 처리해 비교했다. 모든 페이지 라벨이 같았다.
- 합성 세트 페이지 분류 100%(12/12). 검색(dev-hash)은 청크 수가 같고 순위 2곳만 달라졌다.
- 8010 포트로 서버를 띄워 PDF, docx, pptx, xlsx, 여러 페이지 TIFF를 수집했다. 6개 모두 성공했고 페이지 이미지, 요소 위치, 검색, 임베딩 화면이 동작했다.
- 암호 걸린 PDF, DPI가 있거나 없는 이미지, 여러 페이지 TIFF, 회전 페이지의 bbox 위치를 확인했다. 폰트를 못 찾는 경우(CID 폰트)도 텍스트 추출이 된다.
- 설치된 패키지 84개의 라이선스를 확인했다. GPL/AGPL/LGPL 계열은 없다. MPL-2.0은 certifi, orjson 둘이다(파일 단위라 MIT 배포에 문제없음).

### 성능 (149MB, 300페이지 합성 PDF, mock VLM 0.3s, workers 4)

| 조건 | 이전 (PyMuPDF) | 지금 |
|---|---|---|
| VLM 사용 (호출 200회) | 28.9s, 최대 1.1GB | 27.2s, 최대 0.81GB |
| VLM 없음 | 5.6s, 최대 0.6GB | 8.3s, 최대 0.75GB |

VLM이 없을 때는 pdfminer가 순수 Python이라 분석 단계가 2초쯤 느려졌다.

## 3. 다음에 할 일

1. **원본 IngestLens의 새 기능 반영** (원본 세션 작업이 끝난 뒤)
   - 대상: VLM 평가(`scripts/eval_vlm.py`, `make_vlm_set.py`, `make_sample_set.py`, `api/evals.py`, `tools/vlm_checks.py`, "VLM 평가 비교" 화면 `EvalView.tsx`, `evals/vlm/`, `evals/samples/`, `evals/results/`), Docker 실행(`docker-compose.yml`, `docker/`, `config/models.docker*.yaml`, `.dockerignore`), README·HANDOFF·`evals/README.md` 변경.
   - `make_vlm_set.py`, `make_sample_set.py`는 PyMuPDF를 쓴다. `PdfWriter`/pypdfium2로 바꾼다. 색 채운 도형과 HTML 텍스트 상자가 필요해 `PdfWriter`에 기능을 더해야 할 수 있다.
   - 원본 HANDOFF의 "PyMuPDF `korea` 폰트가 영문을 전각 폭으로 그린다" 함정은 MIT 쪽에 맞게 고쳐 넣는다.
   - `evals/samples/`의 외부 PDF 10개는 `SOURCES.md`의 이용 조건을 확인한 뒤 넣는다.
2. **실제 문서로 비교** (HANDOFF §6 P0): 같은 문서를 v1.0.0과 이 버전으로 처리해 라벨, 요소, 표, 그림 영역을 비교한다. 다단 문서, 회전 페이지, 벡터 그림이 많은 페이지를 특히 본다. 차이가 크면 `min_drawings` 등을 `eval_profile.py --sweep`으로 다시 맞춘다.
3. **Linux 서버 확인**: 한글 TrueType 폰트(`fonts-nanum`) 설치, "office font" 결정이 `font_system`/`font_configured`인지, 프로세스 풀 동작.
4. **필요하면 git 이력 정리**: 첫 커밋 `6b6c37b`에 AGPL 전문과 PyMuPDF 코드가 남아 있다. 지금도 문제는 없지만, 이력에서 빼고 싶으면 커밋을 합친다(GitHub에 이미 push했으므로 force push가 필요하다).

## 4. 막혔던 문제와 해결

| 문제 | 원인 | 해결 |
|---|---|---|
| 벤치마크에서 `--vlm-url`을 줘도 VLM 호출이 0회 | `make_pdf`가 `app.tools.pdfgen`을 import하면서 설정이 `RAG_DATA_DIR`/`RAG_MODELS_FILE` 설정 전에 읽혔다 | 환경 변수 설정 뒤에 PDF를 만들도록 순서를 바꿨다. 이 버그로 저장소의 `data/`에 벤치마크 문서 3개가 기록되어 폴더째 지웠다(작업 중 생긴 폴더) |
| 벤치마크 PDF가 150MB가 아니라 102MB | Pillow JPEG가 PyMuPDF보다 픽셀당 바이트가 적다 | 크기 상수를 2.3 → 1.57로 다시 맞춰 `--mb 207`이 약 149MB를 만든다 |
| pdfplumber가 다이어그램 상자를 1×1 표로 잡음 | "lines" 전략은 사각형 하나도 표로 본다 | 2행 2열 미만 표는 버린다(`Page.tables()`) |
| 표 페이지의 텍스트 블록이 PyMuPDF보다 많음 | pdfminer는 표 셀을 각각 블록으로 나눈다 | 표 안 텍스트는 파서가 버리므로 결과는 같다. 그대로 둔다 |
| 회전 페이지 좌표 | PyMuPDF는 회전 전 좌표를 줬고, pdfminer는 회전 후 좌표를 준다 | crop box 기준, 회전 후 좌상단 좌표로 통일했다. 렌더 이미지와 일치함을 확인했다 |
| 회전 결과 세로로 놓인 글이 한 글자씩 줄로 나뉨 | pdfminer `detect_vertical`이 꺼져 있다 | 미해결. 드문 경우라 HANDOFF §9에 적어 두었다 |
| PDFium 동시 렌더 | PDFium은 스레드 안전하지 않다 | 프로세스 안의 렌더를 모듈 lock으로 묶었다. 병렬은 기존처럼 프로세스 풀로 한다 |
| Noto Sans CJK 같은 `.otf` 폰트 | ReportLab은 TrueType(`glyf`) 폰트만 넣을 수 있다 | 등록에 실패하면 다음 후보로 넘어가고 실패 목록을 결정에 남긴다 |
| `eval_retrieval.py`가 끝에 `UnicodeEncodeError` | Windows 콘솔이 cp949라 `—`를 출력하지 못한다(이번 변경과 무관) | 보고서 파일은 정상으로 쓰인다. `PYTHONIOENCODING=utf-8`로 실행하면 피한다 |
| 개발 서버 포트 | 8000번을 다른 프로그램이 쓰고 있었다 | 확인용으로만 앱 8010, mock vLLM 8011을 썼다. 설정 파일은 바꾸지 않았다 |
| 원본 기능 반영 보류 | 원본 IngestLens 폴더에서 다른 Claude 세션이 작업 중이었다(마지막 수정 1분 전) | 반쯤 된 상태를 옮기지 않도록 그 세션이 끝난 뒤 반영하기로 했다 |

## 5. 로컬 환경 메모

- `CLAUDE.md`와 한글 번역본 `CLAUDE_KR.md`는 `.git/info/exclude`에 넣어 커밋하지 않는다.
- venv(`.venv`)에는 PyMuPDF가 없다. `pip install -r backend/requirements-dev.txt`로 새 의존성이 설치된다.
