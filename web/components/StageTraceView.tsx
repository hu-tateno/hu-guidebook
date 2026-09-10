import type { StageTraceOut } from "@/lib/api";

const STAGE_LABELS_JA: Record<string, string> = {
  literal: "1. 文字列検索",
  lexicon_expansion: "2. 辞書展開",
  llm_expansion: "3. LLM検索語追加",
  hybrid: "4. 意味検索統合",
  rerank: "5. 再順位付け",
  answer: "6. 根拠付き回答",
};

export function StageTraceView({ stages }: { stages: StageTraceOut[] }) {
  if (stages.length === 0) return null;
  return (
    <div className="stage-trace" aria-label="検索ステージのトレース">
      {stages.map((stage) => (
        <span key={stage.stage} className="stage-chip" title={stage.query_terms.join(", ")}>
          {STAGE_LABELS_JA[stage.label] ?? `Stage ${stage.stage}`} ({stage.result_count}件)
        </span>
      ))}
    </div>
  );
}
