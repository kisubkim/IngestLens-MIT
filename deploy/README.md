# IngestLens 오프라인 설치

인터넷이 없는 리눅스 서버에 IngestLens를 설치하는 순서다. Docker는 쓰지 않는다.

## 0. 구성

| 구성 요소 | 어디서 | 실행 방법 | GPU |
|---|---|---|---|
| IngestLens 앱 (화면 + 파이프라인) | 앱 서버 | Python venv + uvicorn | 쓰지 않음 |
| 임베딩(bge-m3) + reranker(bge-reranker-v2-m3) | GPU 서버 | **모델 서버 프로세스 1개** (`./model-server.sh start`), root 불필요 | GPU 1장, 프로세스 1개 |
| VLM (예: Qwen3-VL) | 이미 운영 중인 vLLM | 그대로 사용 | 별도 |

- **모델 서버를 따로 두는 이유**
  - vLLM은 프로세스 하나에 모델 하나만 서빙한다. 그래서 임베딩과 reranker를 vLLM으로 띄우면 GPU 프로세스가 2개 필요하다.
  - 그런데 GPU가 Exclusive_Process 모드(프로세스 1개만 허용)이고, root 권한이 없어 모드를 바꿀 수 없다.
  - 모델 서버는 두 모델을 **한 프로세스**에 올리므로, GPU에는 CUDA 컨텍스트가 하나만 생긴다.
- **API:** 모델 서버는 vLLM과 같은 형식을 제공한다(`/v1/embeddings`, `/v1/rerank`, `/tokenize`, `/v1/models`). 앱 쪽은 주소만 적으면 된다.
- **메모리:** 두 모델을 float16으로 올리면 GPU 메모리를 약 2.3GB 쓴다. 80GB GPU면 배치를 크게 잡아도 여유가 있다.

반입할 것:

| 반입할 것 | 만드는 곳 | 크기(대략) |
|---|---|---|
| 소스 (`.venv`, `frontend/node_modules`, `data` 제외) | 이 저장소 | 수십 MB(평가 자료 포함) |
| `wheelhouse/` (Python wheel) | 인터넷 되는 PC에서 `pip download` (2절) | 수백 MB |
| `frontend/dist/` (빌드된 화면) | 인터넷 되는 PC에서 `npm run build` (2절) | 1MB 미만 |
| 모델 폴더 `models/bge-m3`, `models/bge-reranker-v2-m3` | 인터넷 되는 PC에서 Hugging Face로 받기(3절). 이미 있으면 그 폴더를 쓴다 | 각 약 2.3GB |

## 1. 서버 준비

- **앱 서버:** Linux x86_64, Python 3.12. 한글 TrueType 폰트(예: `fonts-nanum`)를 설치하거나 `RAG_CJK_FONT`로 `.ttf` 경로를 지정한다. 없으면 Office 자체 렌더링 페이지 이미지에서 한글이 보이지 않을 수 있다(`docs/HANDOFF.md` 3-2).
- **GPU 서버(모델 서버):** vLLM이 설치된 Python 환경이 있으면 추가로 설치할 것이 없다. 모델 서버는 torch, transformers, fastapi, uvicorn만 쓰는데, 모두 vLLM과 함께 설치되어 있다.
  - vLLM 환경이 없으면 위 네 패키지가 있는 Python 환경이 필요하다. 오프라인이면 wheel을 미리 받아 반입한다.

## 2. 반입 준비 (인터넷 되는 PC)

```bash
# Python wheel. 운영 서버의 OS/CPU/Python 버전에 맞춘다.
pip download -r backend/requirements.txt -d wheelhouse \
  --platform manylinux2014_x86_64 --platform manylinux_2_28_x86_64 \
  --python-version 3.12 --only-binary=:all:
# 화면은 빌드 결과물만 반입한다. 운영 서버에 Node.js가 필요 없다.
cd frontend && npm ci && npm run build
```

## 3. 모델 받기 (인터넷 되는 PC, 없을 때만)

```bash
pip install -U huggingface_hub
hf download BAAI/bge-m3             --local-dir models/bge-m3
hf download BAAI/bge-reranker-v2-m3 --local-dir models/bge-reranker-v2-m3
```

- 이전 버전의 huggingface_hub이면 `huggingface-cli download`를 쓴다.
- vLLM용으로 받아 둔 bge-m3 폴더가 있으면 그대로 쓴다. 같은 Hugging Face 형식이다.
- 라이선스: bge-m3는 MIT, bge-reranker-v2-m3는 Apache-2.0이다. 둘 다 상업 사용이 가능하다.

## 4. 모델 서버 시작 (GPU 서버, root 불필요)

```bash
cd <소스>/deploy
cp model-server.env.example model-server.env
vi model-server.env
./model-server.sh start
./model-server.sh status
```

`model-server.env`에서 고칠 것:

| 항목 | 내용 |
|---|---|
| `PYTHON` | vLLM이 설치된 Python 경로. 예: `~/venvs/vllm/bin/python` |
| `CUDA_VISIBLE_DEVICES` | 남는 GPU 번호(`nvidia-smi`의 번호) |
| `EMBED_MODEL`, `RERANK_MODEL` | 3절의 모델 폴더 경로 |
| `PORT` | 기본 8090 |
| `MAX_BATCH_TOKENS` | 80GB GPU면 65536처럼 크게 잡아도 된다 |

`status`로 확인할 것:
- `/health` 응답에 두 모델이 보이는지
- `nvidia-smi` 목록에 **이 서버의 PID 하나만** GPU를 잡고 있는지

나머지 명령:
- 중지: `./model-server.sh stop`
- 로그: `./model-server.sh logs`
- 문제를 앞에서 직접 보려면: `./model-server.sh run`

서버가 재부팅되면 다시 `start`해야 한다. 자동으로 시작하려면 다음 중 하나를 쓴다(root 불필요).
- `crontab -e`에 `@reboot cd <소스>/deploy && ./model-server.sh start`
- `systemctl --user` 서비스

## 5. 앱 설치와 시작 (앱 서버)

```bash
cd <소스>
python3.12 -m venv .venv
.venv/bin/pip install --no-index --find-links wheelhouse -r backend/requirements.txt
cp deploy/models.yaml config/models.local.yaml
vi config/models.local.yaml
vi .env
cd backend && ../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**`.env`** (저장소 루트)
- `RAG_MODELS_FILE=<소스>/config/models.local.yaml` (절대 경로. 상대 경로는 uvicorn을 실행한 `backend/` 기준으로 풀린다)
- `RAG_API_KEY`: 다른 PC의 사용자는 이 키가 있어야 설정 변경, 문서 삭제, 수집 API를 쓸 수 있다. 반드시 정한다.
- `RAG_DATA_DIR`: 올린 문서, DB, 벡터가 쌓이는 곳. 백업 대상이다. 비우면 `<소스>/data`.

**`config/models.local.yaml`** (`deploy/models.yaml`의 복사본, git에 올라가지 않는다)
- `embedding`, `reranker`의 `base_url`
  - 모델 서버가 같은 서버에서 돌면: `http://localhost:8090/v1`
  - 다른 서버면: `http://<GPU 서버 IP>:8090/v1`
- `model` 이름은 `model-server.env`의 `EMBED_NAME`, `RERANK_NAME`과 같아야 한다.
- `vlm.base_url`, `vlm.model`: 운영 중인 vLLM의 주소와 `--served-model-name`. 이름은 `curl http://<VLM 서버>/v1/models`로 확인한다.
- **Qwen3-VL은 Instruct 버전을 쓴다.** Thinking 버전은 답 앞에 생각 과정을 출력하므로, OCR, 그림 `TYPE:`, 분류 JSON 형식을 기대하는 파서가 잘못 읽을 수 있다.

계속 띄워 두려면 `systemctl --user` 서비스나 `nohup`으로 uvicorn을 실행한다.

## 6. 확인

```bash
curl http://localhost:8000/api/health        # {"ok": true, ...}
```

- 브라우저로 `http://<서버 주소>:8000/#status`를 연다. 임베딩, reranker, VLM이 모두 "정상"인지 본다.
  - "주의": 서버는 응답하지만 `models.yaml`의 모델 이름이 그 서버의 이름과 다르다는 뜻이다.
  - "오류": 연결하지 못한다는 뜻이다. 방화벽, 주소, 포트를 확인한다.
- 문서 하나를 올려 실행해 본다. 실행의 "근거" 탭에서 다음을 확인한다.
  - `embedding model`이 `bge-m3`인지(`dev-hash`가 아닌지)
  - `token estimate`가 측정값(`tokenizer_calibrated`)인지. 모델 서버의 `/tokenize`를 쓴다.
  - Office 문서라면 `office font`가 `font_system`이나 `font_configured`인지
- VLM 품질은 인터넷 되는 PC나 개발 PC에서 같은 VLM 주소로 `scripts/eval_vlm.py`를 돌려 기존 결과와 비교한다.

## 7. 업데이트, 되돌리기, 백업

- **업데이트:** uvicorn을 멈추고 새 소스를 같은 위치에 풀고, 새 `wheelhouse`로 `pip install --no-index --find-links wheelhouse -r backend/requirements.txt`를 다시 실행한 뒤 시작한다.
  - 데이터 폴더, `.env`, `config/models.local.yaml`, `deploy/model-server.env`는 그대로 둔다(덮어쓰지 않는다).
  - 모델 서버가 바뀌었으면 `./model-server.sh stop && ./model-server.sh start`로 다시 띄운다.
- **되돌리기:** 이전 소스와 그 wheelhouse로 같은 순서를 밟는다. 새 버전이 DB에 컬럼을 추가했어도 nullable이라 이전 버전이 읽을 수 있다.
- **백업:** 앱을 멈춘 뒤 `RAG_DATA_DIR` 폴더를 통째로 복사한다.

## 8. 라이선스

- IngestLens는 MIT 라이선스다(`LICENSE`, `NOTICE.md`). 회사 안팎 어디서 쓰든 소스 공개 의무가 없다.
- 설치되는 Python 패키지의 라이선스는 `NOTICE.md`에 있다.
- `evals/samples/*.pdf`는 각 원본의 라이선스를 따른다(`evals/samples/SOURCES.md`).
