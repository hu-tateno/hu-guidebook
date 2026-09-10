"use client";

import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";

pdfjs.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.mjs`;

export interface HighlightBox {
  page: number;
  /** [x0, y0, x1, y1] in PDF points, top-left origin (as produced by PyMuPDF ingestion). */
  bbox: [number, number, number, number];
}

interface RenderedPageSize {
  width: number;
  height: number;
  originalWidth: number;
  originalHeight: number;
}

function HighlightOverlay({ bbox, pageSize }: { bbox: [number, number, number, number]; pageSize: RenderedPageSize }) {
  const scale = pageSize.originalWidth ? pageSize.width / pageSize.originalWidth : 1;
  const [x0, y0, x1, y1] = bbox;
  return (
    <div
      className="pdf-highlight"
      style={{
        left: x0 * scale,
        top: y0 * scale,
        width: Math.max(0, (x1 - x0) * scale),
        height: Math.max(0, (y1 - y0) * scale),
      }}
    />
  );
}

interface PdfViewerProps {
  fileUrl: string;
  page: number;
  highlight?: HighlightBox | null;
  width?: number;
}

export function PdfViewer({ fileUrl, page, highlight, width = 700 }: PdfViewerProps) {
  const [pageSize, setPageSize] = useState<RenderedPageSize | null>(null);

  return (
    <div className="pdf-viewer">
      <Document
        file={fileUrl}
        loading={<p className="muted">PDFを読み込み中...</p>}
        error={<p className="error-text">PDFを読み込めませんでした</p>}
      >
        <div style={{ position: "relative" }}>
          <Page
            key={page}
            pageNumber={page}
            width={width}
            renderTextLayer={false}
            renderAnnotationLayer={false}
            onRenderSuccess={(rendered) =>
              setPageSize({
                width: rendered.width,
                height: rendered.height,
                originalWidth: rendered.originalWidth,
                originalHeight: rendered.originalHeight,
              })
            }
          />
          {highlight && highlight.page === page && pageSize && (
            <HighlightOverlay bbox={highlight.bbox} pageSize={pageSize} />
          )}
        </div>
      </Document>
    </div>
  );
}
