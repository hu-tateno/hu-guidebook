"use client";

import { useEffect, useState } from "react";
import {
  DocumentOut,
  EvaluationStats,
  LowRatedQuestion,
  adminExportCsvUrl,
  adminLogin,
  adminLogout,
  adminLowRatedQuestions,
  adminMetrics,
  listDocuments,
} from "@/lib/api";

export default function AdminPage() {
  const [password, setPassword] = useState("");
  const [loggedIn, setLoggedIn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [admissionYear, setAdmissionYear] = useState<number | undefined>(undefined);
  const [metrics, setMetrics] = useState<EvaluationStats | null>(null);
  const [lowRated, setLowRated] = useState<LowRatedQuestion[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listDocuments()
      .then(setDocuments)
      .catch(() => undefined);
  }, []);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await adminLogin(password);
      setLoggedIn(true);
      setPassword("");
    } catch {
      setError("パスワードが違います。管理APIが有効化されているかも確認してください。");
    }
  }

  async function handleLogout() {
    await adminLogout().catch(() => undefined);
    setLoggedIn(false);
    setMetrics(null);
    setLowRated([]);
  }

  useEffect(() => {
    if (!loggedIn) return;
    setLoading(true);
    Promise.all([adminMetrics({ admissionYear }), adminLowRatedQuestions({ admissionYear, limit: 50 })])
      .then(([m, lr]) => {
        setMetrics(m);
        setLowRated(lr);
      })
      .catch(() => setError("データの取得に失敗しました。"))
      .finally(() => setLoading(false));
  }, [loggedIn, admissionYear]);

  if (!loggedIn) {
    return (
      <main className="page">
        <div className="header">
          <h1>管理ダッシュボード</h1>
        </div>
        <form className="search-form panel" onSubmit={handleLogin}>
          <input
            type="password"
            placeholder="管理者パスワード"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-label="管理者パスワード"
          />
          <button type="submit" disabled={!password}>
            ログイン
          </button>
        </form>
        {error && <p className="error-text">{error}</p>}
      </main>
    );
  }

  return (
    <main className="page">
      <div className="header">
        <h1>管理ダッシュボード</h1>
        <button className="btn secondary" type="button" onClick={handleLogout}>
          ログアウト
        </button>
      </div>

      <div className="panel search-form">
        <select
          value={admissionYear ?? ""}
          onChange={(e) => setAdmissionYear(e.target.value ? Number(e.target.value) : undefined)}
          aria-label="年度で絞り込み"
        >
          <option value="">全年度</option>
          {documents.map((d) => (
            <option key={d.id} value={d.admission_year}>
              {d.admission_year}年度
            </option>
          ))}
        </select>
        <a className="btn secondary" href={adminExportCsvUrl(admissionYear)}>
          CSVをダウンロード
        </a>
      </div>

      {error && <p className="error-text">{error}</p>}
      {loading && <p className="muted">読み込み中...</p>}

      {metrics && (
        <div className="metric-grid">
          <div className="metric-card">
            <div className="value">{metrics.total_searches}</div>
            <div className="label">検索回数</div>
          </div>
          <div className="metric-card">
            <div className="value">{metrics.total_evaluations}</div>
            <div className="label">評価件数</div>
          </div>
          <div className="metric-card">
            <div className="value">{formatRate(metrics.helpful_rate)}</div>
            <div className="label">検索が役に立った割合</div>
          </div>
          <div className="metric-card">
            <div className="value">{formatRate(metrics.resolved_rate)}</div>
            <div className="label">AI回答で解決した割合</div>
          </div>
        </div>
      )}

      <div className="panel">
        <h2 style={{ fontSize: "1rem", marginTop: 0 }}>低評価の質問</h2>
        {lowRated.length === 0 ? (
          <p className="muted">低評価の質問はありません。</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>年度</th>
                  <th>質問</th>
                  <th>候補</th>
                  <th>回答解決</th>
                  <th>カテゴリ</th>
                  <th>コメント</th>
                </tr>
              </thead>
              <tbody>
                {lowRated.map((row) => (
                  <tr key={row.evaluation_id}>
                    <td>{row.admission_year}</td>
                    <td>{row.query_text}</td>
                    <td>{formatBool(row.suggestion_helpful)}</td>
                    <td>{formatBool(row.answer_resolved)}</td>
                    <td>{row.category ?? "-"}</td>
                    <td>{row.comment ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}

function formatRate(rate: number | null): string {
  if (rate == null) return "-";
  return `${Math.round(rate * 100)}%`;
}

function formatBool(value: boolean | null): string {
  if (value == null) return "-";
  return value ? "◯" : "×";
}
