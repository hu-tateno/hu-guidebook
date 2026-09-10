import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StageTraceView } from "@/components/StageTraceView";

describe("StageTraceView", () => {
  it("renders nothing when there are no stages", () => {
    const { container } = render(<StageTraceView stages={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a chip per stage with a Japanese label and result count", () => {
    render(
      <StageTraceView
        stages={[
          { stage: 1, label: "literal", query_terms: ["休学"], result_count: 3 },
          { stage: 5, label: "rerank", query_terms: ["休学"], result_count: 5 },
        ]}
      />
    );
    expect(screen.getByText(/1\. 文字列検索/)).toBeInTheDocument();
    expect(screen.getByText(/\(3件\)/)).toBeInTheDocument();
    expect(screen.getByText(/5\. 再順位付け/)).toBeInTheDocument();
  });

  it("falls back to a generic label for an unknown stage label", () => {
    render(<StageTraceView stages={[{ stage: 9, label: "mystery", query_terms: [], result_count: 0 }]} />);
    expect(screen.getByText(/Stage 9/)).toBeInTheDocument();
  });
});
