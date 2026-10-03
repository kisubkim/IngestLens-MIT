# 라이선스 고지

2026-10-03 기준이다. 이 저장소의 라이선스와, 설치할 때 받아 오는 의존성의 라이선스를 구분한다. 버전은 `backend/requirements.txt`, `backend/requirements-dev.txt`, `frontend/package-lock.json`에 적힌 값을 따른다.

모델 가중치, `.venv`, `node_modules`, `frontend/dist`, `data/`, `.env`는 이 저장소에 포함하지 않는다.

## 1. 이 저장소

Copyright (C) 2026 김기섭

이 저장소의 소스, 문서, 설정, 합성 평가 세트, 화면 캡처는 [GNU Affero General Public License v3.0](https://www.gnu.org/licenses/agpl-3.0.html)(AGPL-3.0-only)으로 배포한다. 전문은 `LICENSE`에 있다. 대상은 `backend/`, `frontend/src`, `scripts/`, `config/`, `docs/`, `evals/`, `captures/`, `README.md`다.

AGPL-3.0을 고른 이유는 핵심 의존성인 PyMuPDF(2절)를 AGPL 조건으로 쓰기 때문이다.

- 수정한 버전을 배포하거나, 네트워크로 사용자에게 서비스하면 그 사용자에게 해당 버전의 소스를 제공해야 한다(13조).
- 이 프로그램과 HTTP, 파일, DB로 데이터만 주고받는 별도 프로그램(예: vLLM, Open WebUI)은 이 라이선스의 영향을 받지 않는다. 이 프로그램이 만든 결과 데이터(청크, 임베딩)에도 일반적으로 적용되지 않는다고 본다. 다만 청크 텍스트는 원본 문서의 권리를 따른다.

## 2. PyMuPDF

`pymupdf==1.28.2`는 Artifex Software의 이중 라이선스다. 설치본 `COPYING`의 문구는 다음과 같다.

`Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License`

- 오픈소스: [GNU AGPL 3.0](https://www.gnu.org/licenses/agpl-3.0.html). 이 저장소가 따르는 조건이다.
- 상용: [Artifex 상업 라이선스](https://artifex.com/licensing)

이 저장소는 PyMuPDF의 소스와 바이너리를 담고 있지 않다. `requirements.txt`로 설치한다. 파싱, 페이지 렌더, Office 자체 렌더링이 PyMuPDF를 직접 호출한다.

## 3. Python 직접 의존성

실행에 필요하다. 모두 퍼미시브 라이선스다. PyMuPDF만 2절의 이중 라이선스다.

| 패키지 | 버전 | 라이선스 |
|---|---|---|
| fastapi | 0.142.1 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| sse-starlette | 3.5.0 | BSD-3-Clause |
| python-multipart | 0.0.32 | Apache-2.0 |
| pydantic-settings | 2.15.0 | MIT |
| SQLAlchemy | 2.1.1 | MIT |
| pymupdf | 1.28.2 | AGPL-3.0 또는 Artifex 상업 라이선스 |
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

같이 설치되는 라이브러리 가운데 카피레프트가 하나 있다. `langgraph-sdk`가 요구하는 `orjson`은 `MPL-2.0 AND (Apache-2.0 OR MIT)`다. MPL-2.0은 orjson 파일 자체에 적용된다. 이 저장소의 소스 전체에 AGPL처럼 퍼지지는 않는다. 그 외 `langchain-core`(MIT), `lxml`(BSD-3-Clause), `Pillow`(MIT-CMU), `grpcio`(Apache-2.0), `protobuf`(BSD-3-Clause) 같은 간접 의존성은 설치 환경에만 있고 소스 트리에는 없다.

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
