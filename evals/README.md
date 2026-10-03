# 평가와 튜닝 (M6)

규칙과 모델 설정을 바꾸기 전과 후에 같은 데이터로 측정해서 비교하기 위한 도구다.
합성 세트(`synthetic/`)는 바로 실행할 수 있는 예시다. 튜닝은 **실제로 처리할 문서에 직접 라벨을 붙인 세트**로 해야 의미가 있다.

## 1. 페이지 분류 평가: `scripts/eval_profile.py`

```bash
.venv/Scripts/python scripts/eval_profile.py --labels evals/synthetic/profile_labels.json --sweep --out evals/reports/profile_<이름>.md
```

라벨 파일 형식은 아래와 같다. 페이지 번호는 1부터 센다. `file`은 라벨 파일 기준 상대 경로다.

```json
{"documents": [{"file": "manual.pdf", "pages": {"1": "text", "9": "table", "11": "scanned"}}]}
```

- 라벨 값은 `text`, `scanned`, `table`, `diagram`, `chart`, `image_heavy`, `mixed` 중 하나다.
- 평가 대상은 규칙(`config/strategy_rules.yaml`의 `profiler`)뿐이다. VLM 2차 판단은 제외한다.
- 결과: 정확도, 혼동 행렬, 틀린 페이지와 그 feature 값.
- `--sweep`: 규칙의 모든 임계값을 좌표 하강법으로 바꿔 보며 정확도가 오르는 변경을 **제안만** 한다. 설정 파일은 고치지 않는다.
  - 라벨이 적으면 과적합된다. 제안을 그대로 쓰기보다, 틀린 페이지의 feature를 보고 규칙이나 feature를 새로 만드는 편이 낫다.
  - 예: M6에서 추가한 `table_text_share` 규칙.

## 2. 검색 품질 평가: `scripts/eval_retrieval.py`

```bash
.venv/Scripts/python scripts/eval_retrieval.py --dataset evals/synthetic/retrieval.json --models config/models.yaml --out evals/reports/retrieval_<이름>.md
```

데이터셋 형식은 아래와 같다.

```json
{"documents": [{"file": "manual.pdf", "queries": [
  {"q": "냉각수 온도 유지 범위", "pages": [1], "kind": "lexical"},
  {"q": "설치 전에 준비할 것", "text": "전원 케이블", "kind": "paraphrase"}]}]}
```

- 정답 판정: 검색 결과가 `pages`(1부터 셈) 중 하나를 포함하거나, 본문에 `text`가 들어 있으면 정답이다.
- `kind`: 질의의 성격이다. 결과를 이 값별로 나눠 보여준다.
  - `lexical`: 문서의 단어를 그대로 쓴 질의
  - `paraphrase`: 다른 말로 바꿔 쓴 질의
  - 다른 값을 써도 된다.
- 동작: 문서마다 파이프라인 전체를 임시 data dir에서 실행한다. 그다음 dense, lexical, hybrid 방식으로 검색하고, reranker가 설정되어 있으면 hybrid+rerank도 실행한다.
- 지표: hit@1, hit@k, MRR@k.
- `--models`로 다른 `models.yaml`을 지정하면 모델끼리 비교할 수 있다.

## 3. 튜닝 순서

1. 실제 문서 5~20개를 고른다. 형식과 유형이 골고루 섞이게 한다.
2. 페이지 라벨 파일과 질의 20~50개를 만든다. 질의에는 문서 단어를 그대로 쓴 것과 바꿔 쓴 것을 섞는다.
3. 기준선을 측정한다. 두 스크립트를 실행하고 보고서를 `evals/reports/`에 저장한다.
4. 규칙, 모델, 청킹 파라미터 중 **하나만** 바꾼다.
5. 다시 측정하고 기준선과 비교한다. 좋아졌으면 유지하고, 결과를 `docs/HANDOFF.md`의 측정 기록 표에 추가한다.

## 현재 기준선 (합성 세트, 2026-09-30)

| 설정 | 페이지 분류 정확도 | hybrid hit@1 (전체 / 바꿔 쓴 질의) |
|---|---|---|
| dev-hash 임베딩, VLM 없음 | 100% (12페이지) | 82% / 62% |

- 보고서: `reports/profile_synthetic.md`, `reports/retrieval_synthetic_devhash.md`, `reports/retrieval_synthetic_mockhttp.md`
- 합성 세트는 규칙을 만든 사람이 만든 데이터라서 점수가 높게 나온다. 실제 문서 기준선을 새로 만들어야 한다.
- 바꿔 쓴 질의가 약한 것은 dev-hash가 의미를 모르기 때문이다. 실제 임베딩 모델(bge-m3 등)을 연결하면 가장 먼저 이 수치를 확인한다.
