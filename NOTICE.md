# 라이선스 고지

2026-10-04 기준이다. 이 저장소의 라이선스와, 설치할 때 받아 오는 의존성의 라이선스를 구분한다. 버전은 `backend/requirements.txt`, `backend/requirements-dev.txt`, `frontend/package-lock.json`에 적힌 값을 따른다.

모델 가중치, `.venv`, `node_modules`, `frontend/dist`, `data/`, `.env`는 이 저장소에 포함하지 않는다.

## 1. 이 저장소

Copyright (c) 2026 김기섭

이 저장소의 소스, 문서, 설정, 합성 평가 세트, 화면 캡처는 [MIT License](https://opensource.org/license/mit)로 배포한다. 전문은 `LICENSE`에 있다. 대상은 `backend/`, `frontend/src`, `scripts/`, `config/`, `docs/`, `evals/`, `captures/`, `README.md`다.

- 저작권 표시와 허락 문구(`LICENSE`)를 함께 두면 사용, 수정, 배포, 상업적 이용이 모두 가능하다. 수정한 버전의 소스를 공개할 의무는 없다.
- 이 프로그램이 만든 결과 데이터(청크, 임베딩)에는 이 라이선스가 적용되지 않는다. 청크 텍스트는 원본 문서의 권리를 따른다.

### AGPL에서 MIT로 바꾼 경위

v1.0.0은 PyMuPDF(AGPL-3.0 또는 Artifex 상업 라이선스)를 핵심 의존성으로 써서 AGPL-3.0으로 배포했다. 이 저장소는 PyMuPDF를 걷어 내고 2절의 퍼미시브 라이브러리로 바꾼 뒤 MIT로 배포한다.

- PyMuPDF는 `requirements.txt`에서 빠졌고, 소스 어디에서도 import하지 않는다.
- 이미 AGPL-3.0으로 받은 v1.0.0 사본은 그 사본의 조건(AGPL-3.0)을 그대로 따른다. 라이선스 변경은 이 저장소의 이후 버전에만 적용된다.

## 2. PDF 처리 라이브러리

PyMuPDF가 하던 일을 다음 라이브러리가 나눠 맡는다. 모두 퍼미시브 라이선스다.

| 역할 | 패키지 | 라이선스 |
|---|---|---|
| 페이지 구조 읽기(텍스트 블록, 글자 크기, 이미지, 벡터 경로) | pdfminer.six | MIT |
| 괘선 표 찾기, 좌표 변환 | pdfplumber | MIT |
| 페이지 렌더, 크롭, 페이지 수, 암호 확인 | pypdfium2 | Apache-2.0 또는 BSD-3-Clause |
| PDF 쓰기(이미지 감싸기, Office 자체 렌더링, 합성 문서) | reportlab | BSD-3-Clause |
| 이미지 디코딩, PNG/JPEG 인코딩 | Pillow | MIT-CMU |

pypdfium2 wheel에는 PDFium 바이너리가 들어 있다. PDFium은 BSD-3-Clause 계열이고, 함께 빌드된 FreeType(FreeType License, FTL 선택), AGG 2.3, libjpeg-turbo(IJG, BSD-3-Clause), OpenJPEG(BSD-2-Clause), libpng, libtiff, zlib, Little CMS(MIT), ICU(Unicode-3.0), Abseil(Apache-2.0)도 모두 퍼미시브다. 전문은 설치본의 `pypdfium2-*.dist-info/licenses/`에 있다. 바이너리를 다시 배포할 때는 이 고지 파일들을 함께 넣는다.

### 한글 폰트

자체 렌더링이 쓰는 한글 폰트는 이 저장소에 넣지 않는다. 실행하는 PC에 있는 TrueType 폰트(`RAG_CJK_FONT`, 없으면 맑은 고딕·나눔고딕 등 시스템 폰트)를 PDF에 포함한다. 그 폰트의 라이선스는 설치된 폰트를 따른다. 나눔고딕은 SIL Open Font License 1.1이고, 맑은 고딕은 Windows에 딸린 폰트다. 찾지 못하면 폰트를 포함하지 않는 ReportLab 내장 CID 폰트 이름만 쓴다.

## 3. Python 직접 의존성

실행에 필요하다. 모두 퍼미시브 라이선스다.

| 패키지 | 버전 | 라이선스 |
|---|---|---|
| fastapi | 0.142.1 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| sse-starlette | 3.5.0 | BSD-3-Clause |
| python-multipart | 0.0.32 | Apache-2.0 |
| pydantic-settings | 2.15.0 | MIT |
| SQLAlchemy | 2.1.1 | MIT |
| pypdfium2 | 5.13.0 | Apache-2.0 또는 BSD-3-Clause (PDFium 바이너리 포함, 2절) |
| pdfplumber | 0.11.10 | MIT |
| pdfminer.six | 20260107 | MIT |
| reportlab | 5.0.1 | BSD-3-Clause |
| pillow | 12.3.0 | MIT-CMU |
| langgraph | 1.2.12 | MIT |
| qdrant-client | 1.19.1 | Apache-2.0 |
| openai | 3.22.1 | Apache-2.0 |
| filetype | 1.2.0 | MIT |
| PyYAML | 6.0.3 | MIT |
| numpy | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| python-docx | 1.2.0 | MIT |
| python-pptx | 1.0.2 | MIT |
| openpyxl | 3.1.5 | MIT |
| httpx | 0.28.1 | BSD-3-Clause |

개발 전용이다.

| 패키지 | 버전 | 라이선스 |
|---|---|---|
| pytest | 9.1.1 | MIT |
| psutil | 7.2.2 | BSD-3-Clause |

같이 설치되는 라이브러리 가운데 약한 카피레프트(MPL-2.0)가 둘 있다. `langgraph-sdk`가 요구하는 `orjson`(`MPL-2.0 AND (Apache-2.0 OR MIT)`)과 `httpx`가 요구하는 `certifi`(MPL-2.0)다. MPL-2.0은 해당 패키지 파일에만 적용되며, 그 파일을 수정하지 않는 한 이 저장소의 MIT 소스에는 영향이 없다. 그 외 `pdfminer.six`가 요구하는 `cryptography`(Apache-2.0 또는 BSD-3-Clause)·`charset-normalizer`(MIT), `langchain-core`(MIT), `lxml`(BSD-3-Clause), `grpcio`(Apache-2.0), `protobuf`(BSD-3-Clause) 같은 간접 의존성은 설치 환경에만 있고 소스 트리에는 없다. 설치된 84개 패키지의 메타데이터를 확인했고 GPL/AGPL/LGPL 계열은 없다.

## 4. 프론트엔드

`frontend/package-lock.json` 기준이다. `node_modules`와 `frontend/dist`는 저장소에 넣지 않는다.

| 패키지 | 버전 | 용도 | 라이선스 |
|---|---|---|---|
| react | 19.3.0 | 실행 | MIT |
| react-dom | 19.3.0 | 실행 | MIT |
| typescript | 5.9.3 | 개발 | Apache-2.0 |
| vite | 8.3.1 | 개발 | MIT |
| @vitejs/plugin-react | 6.1.1 | 개발 | MIT |
| @types/react | 19.3.0 | 개발 | MIT |
| @types/react-dom | 19.3.0 | 개발 | MIT |

Vite가 개발 의존성으로 받는 `lightningcss` 1.33.0은 MPL-2.0이다. 이것도 해당 패키지 파일에 한정된다. 빌드된 CSS를 이 저장소에 넣지는 않는다.

## 5. 이 저장소에 없는 모델과 도구

권장 모델은 받아서 쓰는 가중치다. 배포하거나 반입하기 전에 해당 모델 카드를 다시 확인한다.

| 모델 | 용도 | 모델 카드에 적힌 라이선스 |
|---|---|---|
| [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) | 임베딩 | MIT |
| [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | rerank | Apache-2.0 |
| [Qwen/Qwen2.5-VL-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct) | VLM | Apache-2.0 |

LibreOffice는 선택 설치다. 문서 변환에 쓸 때만 필요하며 [MPL-2.0](https://www.libreoffice.org/about-us/licenses/)이다. Ollama를 개발 PC에서 쓰는 경우에도 그 프로그램과 받아 둔 모델의 라이선스를 따로 따른다.
