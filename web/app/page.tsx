"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import {
  ChunkOut,
  DocumentOut,
  SearchResponse,
  documentFileUrl,
  listDocuments,
  recordHighlight,
  search as runSearch,
  submitEvaluation,
} from "@/lib/api";
import { getOrCreateDeviceId } from "@/lib/device";
import { StageTraceView } from "@/components/StageTraceView";

// react-pdf/pdfjs-dist touches browser-only globals (DOMMatrix, canvas) at module load
// time, so it must never be evaluated on the server — including during static prerender.
const PdfViewer = dynamic(() => import("@/components/PdfViewer").then((m) => m.PdfViewer), {
  ssr: false,
  loading: () => <p className="muted">PDFビューアを読み込み中...</p>,
});

export default function HomePage() {
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [admissionYear, setAdmissionYear] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [deviceId, setDeviceId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [selectedChunk, setSelectedChunk] = useState<ChunkOut | null>(null);
  const [highlightedIds, setHighlightedIds] = useState<Set<number>>(new Set());
  const [evaluation, setEvaluation] = useState<{ helpful?: boolean; resolved?: boolean } | null>(null);

  useEffect(() => {
    setDeviceId(getOrCreateDeviceId());
    listDocuments()
      .then((docs) => {
        setDocuments(docs);
        if (docs.length > 0) setAdmissionYear(docs[0].admission_year);
      })
      .catch(() => setError("年度一覧を取得できませんでした。APIが起動しているか確認してください。"));
  }, []);

  const selectedDocument = useMemo(
    () => documents.find((d) => d.admission_year === admissionYear) ?? null,
    [documents, admissionYear]
  );

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!admissionYear || !query.trim()) return;
    setLoading(true);
    setError(null);
    setEvaluation(null);
    try {
      const response = await runSearch({ admissionYear, query: query.trim(), deviceId });
      setResult(response);
      setSelectedChunk(response.results[0] ?? null);
    } catch {
      setError("検索に失敗しました。時間をおいて再度お試しください。");
    } finally {
      setLoading(false);
    }
  }

  async function handleHighlight(chunk: ChunkOut) {
    setHighlightedIds((prev) => new Set(prev).add(chunk.chunk_id));
    try {
      await recordHighlight({ chunkId: chunk.chunk_id, deviceId });
    } catch {
      // best-effort; highlight recording failure shouldn't block reading
    }
  }

  async function handleEvaluate(field: "helpful" | "resolved", value: boolean) {
    if (!result) return;
    const next = { ...evaluation, [field]: value };
    setEvaluation(next);
    try {
      await submitEvaluation({
        searchQueryId: result.search_query_id,
        suggestionHelpful: next.helpful,
        answerResolved: next.resolved,
        deviceId,
      });
    } catch {
      // best-effort
    }
  }

  return (
    <main className="page">
      <div className="header">
        <h1>履修の手引き読解支援システム</h1>
        <span className="sub">入学年度別の履修の手引きを、段階的な検索と根拠付き回答で読む教材アプリ</span>
      </div>

      <form className="search-form panel" onSubmit={handleSearch}>
        <select
          value={admissionYear ?? ""}
          onChange={(e) => setAdmissionYear(Number(e.target.value))}
          aria-label="入学年度"
        >
          {documents.map((d) => (
            <option key={d.id} value={d.admission_year}>
              {d.admission_year}年度
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="質問を入力（例: 休学したい場合はどうすればいいですか）"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="検索キーワード"
        />
        <button type="submit" disabled={loading || !admissionYear || !query.trim()}>
          {loading ? "検索中..." : "検索"}
        </button>
      </form>

      {error && <p className="error-text">{error}</p>}

      {result && (
        <>
          <StageTraceView stages={result.stages} />

          {result.answer && (
            <div className="panel">
              <div className="answer-panel">{result.answer}</div>
              <div className="eval-row">
                <span className="muted">この回答で解決しましたか？</span>
                <button
                  className={evaluation?.resolved === true ? "active-yes" : ""}
                  onClick={() => handleEvaluate("resolved", true)}
                  type="button"
                >
                  解決した
                </button>
                <button
                  className={evaluation?.resolved === false ? "active-no" : ""}
                  onClick={() => handleEvaluate("resolved", false)}
                  type="button"
                >
                  解決しなかった
                </button>
              </div>
            </div>
          )}

          <div className="panel">
            <div className="eval-row">
              <span className="muted">検索結果は参考になりましたか？</span>
              <button
                className={evaluation?.helpful === true ? "active-yes" : ""}
                onClick={() => handleEvaluate("helpful", true)}
                type="button"
              >
                役に立った
              </button>
              <button
                className={evaluation?.helpful === false ? "active-no" : ""}
                onClick={() => handleEvaluate("helpful", false)}
                type="button"
              >
                役に立たなかった
              </button>
            </div>
          </div>

          <div style={{ display: "flex", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 360px", minWidth: 300 }}>
              <ul className="result-list">
                {result.results.map((chunk) => (
                  <li
                    key={chunk.chunk_id}
                    className="result-item"
                    style={{ borderColor: selectedChunk?.chunk_id === chunk.chunk_id ? "var(--accent)" : undefined }}
                  >
                    <div className="meta">
                      <span>p.{chunk.page_number}</span>
                      <span>score {chunk.score.toFixed(2)}</span>
                    </div>
                    <p className="snippet">{chunk.text}</p>
                    <div className="result-actions">
                      <button type="button" onClick={() => setSelectedChunk(chunk)}>
                        PDFで見る
                      </button>
                      <button
                        type="button"
                        className={highlightedIds.has(chunk.chunk_id) ? "active" : ""}
                        onClick={() => handleHighlight(chunk)}
                      >
                        {highlightedIds.has(chunk.chunk_id) ? "ハイライト済み" : "ハイライトする"}
                      </button>
                    </div>
                  </li>
                ))}
                {result.results.length === 0 && <p className="muted">該当する記述が見つかりませんでした。</p>}
              </ul>
            </div>

            <div style={{ flex: "1 1 420px", minWidth: 320 }}>
              {selectedDocument && selectedChunk && (
                <PdfViewer
                  fileUrl={documentFileUrl(selectedDocument.source_filename)}
                  page={selectedChunk.page_number}
                  highlight={{ page: selectedChunk.page_number, bbox: selectedChunk.bbox }}
                />
              )}
            </div>
          </div>
        </>
      )}
    </main>
  );
}
