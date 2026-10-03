import { useEffect, useState } from "react";
import { api, type StorageItem, type StorageKey, type StorageState } from "./api";

const SOURCE_LABEL: Record<StorageItem["source"], string> = {
  env: "환경 변수",
  dotenv: ".env",
  file: "설정 파일",
  default: "기본값",
};

const PLACEHOLDER: Record<StorageKey, string> = {
  data_dir: "비우면 기본값 (저장소의 data/)",
  db_url: "비우면 데이터 폴더의 SQLite. 예: postgresql+psycopg://user:pass@host:5432/rag",
  qdrant_url: "비우면 데이터 폴더의 내장 Qdrant. 예: http://qdrant:6333",
};

function fmtBytes(bytes: number | null) {
  if (bytes === null) return "없음";
  if (bytes >= 2 ** 30) return `${(bytes / 2 ** 30).toFixed(1)} GB`;
  if (bytes >= 2 ** 20) return `${(bytes / 2 ** 20).toFixed(1)} MB`;
  return `${Math.ceil(bytes / 1024)} KB`;
}

export default function SettingsView() {
  const [state, setState] = useState<StorageState | null>(null);
  const [draft, setDraft] = useState<Partial<Record<StorageKey, string>>>({});
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = () => api.storage().then(setState).catch((e) => setError(String(e)));
  useEffect(() => {
    load();
  }, []);

  if (!state) return <div className="placeholder">{error ?? "불러오는 중…"}</div>;

  const dirty = Object.keys(draft).length > 0;
  const canEdit = state.editable_here || state.key_required;

  const save = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      setState(await api.updateStorage(draft, apiKey || undefined));
      setDraft({});
      setSaved(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="settings">
      <h2>저장 위치</h2>
      {error && <div className="error-box">{error}</div>}
      {state.restart_required && (
        <div className="notice">
          변경한 설정은 <b>서버를 재시작해야</b> 적용됩니다. 기존 데이터는 자동으로 옮기지 않습니다. 서버를 멈춘 뒤 지금 데이터 폴더를
          통째로 새 위치에 복사하면 그대로 이어서 쓸 수 있습니다.
          {state.active_runs > 0 && ` 지금 실행 중이거나 대기 중인 작업이 ${state.active_runs}개 있으니 끝난 뒤 재시작하세요.`}
        </div>
      )}

      <section className="card">
        <h3>현재 사용 중</h3>
        <table className="settings-table">
          <thead>
            <tr>
              <th>항목</th>
              <th>위치</th>
              <th>용량</th>
            </tr>
          </thead>
          <tbody>
            {state.usage.map((u) => (
              <tr key={u.key}>
                <td>{u.label}</td>
                <td className="mono">{u.path}</td>
                <td>{fmtBytes(u.bytes)}</td>
              </tr>
            ))}
            {!state.usage.some((u) => u.key === "db") && (
              <tr>
                <td>DB (외부)</td>
                <td className="mono">{state.database}</td>
                <td>—</td>
              </tr>
            )}
            {!state.usage.some((u) => u.key === "qdrant") && (
              <tr>
                <td>Qdrant (외부)</td>
                <td className="mono">{state.vector_store}</td>
                <td>—</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h3>변경</h3>
        {!canEdit && (
          <p className="muted">
            이 서버가 돌아가는 PC에서 접속했을 때만 바꿀 수 있습니다. 다른 PC에서 바꾸려면 서버에 RAG_API_KEY를 설정하세요.
          </p>
        )}
        {state.items.map((item) => (
          <div key={item.key} className="setting-row">
            <label htmlFor={`set-${item.key}`}>
              {item.label}
              <span className="badge">{SOURCE_LABEL[item.source]}</span>
              {item.pending && <span className="badge pending">재시작 후 적용</span>}
            </label>
            <input
              id={`set-${item.key}`}
              className="mono"
              value={draft[item.key] ?? (item.source === "default" ? "" : item.configured)}
              placeholder={PLACEHOLDER[item.key]}
              disabled={item.locked || !canEdit}
              onChange={(e) => {
                setSaved(false);
                setDraft((d) => ({ ...d, [item.key]: e.target.value }));
              }}
            />
            <div className="muted">
              {item.locked
                ? `RAG_${item.key.toUpperCase()}가 ${SOURCE_LABEL[item.source]}로 설정되어 있어 여기서 바꿀 수 없습니다.`
                : item.pending
                  ? `지금 사용 중: ${item.effective}`
                  : null}
            </div>
          </div>
        ))}
        {state.key_required && (
          <div className="setting-row">
            <label htmlFor="set-key">관리자 키 (RAG_API_KEY)</label>
            <input id="set-key" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
          </div>
        )}
        <div className="setting-actions">
          <button className="primary" disabled={!dirty || saving || !canEdit} onClick={save}>
            {saving ? "저장 중…" : "저장"}
          </button>
          <button disabled={!dirty || saving} onClick={() => setDraft({})}>
            되돌리기
          </button>
          {saved && <span className="muted">저장했습니다.</span>}
        </div>
        <p className="muted">
          설정 파일: <span className="mono">{state.settings_file}</span>. 환경 변수와 .env가 이 파일보다 우선합니다.
        </p>
      </section>
    </div>
  );
}
