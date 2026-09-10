import { afterEach, describe, expect, it, vi } from "vitest";
import { adminExportCsvUrl, documentFileUrl, popularHighlights, search, submitEvaluation } from "@/lib/api";

function mockFetchOnce(body: unknown, ok = true) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 500,
    statusText: ok ? "OK" : "Error",
    json: async () => body,
    text: async () => JSON.stringify(body),
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("search()", () => {
  it("posts admission_year/query/device_id and returns the parsed response", async () => {
    const fetchMock = mockFetchOnce({
      search_query_id: 1,
      admission_year: 2024,
      document_id: 1,
      query: "休学",
      stages: [],
      results: [],
      answer: null,
    });

    const result = await search({ admissionYear: 2024, query: "休学", deviceId: "device-abc" });

    expect(result.search_query_id).toBe(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/search");
    const body = JSON.parse(init.body as string);
    expect(body).toMatchObject({ admission_year: 2024, query: "休学", device_id: "device-abc", want_answer: true });
  });

  it("throws on a non-ok response", async () => {
    mockFetchOnce({ detail: "not found" }, false);
    await expect(search({ admissionYear: 1999, query: "x", deviceId: "d" })).rejects.toThrow();
  });
});

describe("submitEvaluation()", () => {
  it("sends device_id as part of the request body (never in a header/URL)", async () => {
    const fetchMock = mockFetchOnce({ status: "ok" });
    await submitEvaluation({ searchQueryId: 5, suggestionHelpful: true, deviceId: "device-xyz" });

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).not.toContain("device-xyz");
    const body = JSON.parse(init.body as string);
    expect(body.device_id).toBe("device-xyz");
  });
});

describe("popularHighlights()", () => {
  it("builds a query string from admissionYear/documentId/limit", async () => {
    const fetchMock = mockFetchOnce([]);
    await popularHighlights({ admissionYear: 2024, documentId: 3, limit: 5 });
    const [url] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("admission_year=2024");
    expect(String(url)).toContain("document_id=3");
    expect(String(url)).toContain("limit=5");
  });
});

describe("URL builders", () => {
  it("documentFileUrl points at the API's file endpoint", () => {
    expect(documentFileUrl(7)).toBe("http://localhost:8000/api/documents/7/file");
  });

  it("adminExportCsvUrl omits admission_year when not given", () => {
    expect(adminExportCsvUrl()).toBe("http://localhost:8000/api/admin/export.csv");
    expect(adminExportCsvUrl(2025)).toBe("http://localhost:8000/api/admin/export.csv?admission_year=2025");
  });
});
