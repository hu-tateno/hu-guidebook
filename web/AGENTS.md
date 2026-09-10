# web/ instructions

Next.js (App Router, TypeScript) frontend. See root `AGENTS.md` first.

## Layout

- `app/page.tsx` — search + PDF viewer + highlight + evaluation UI (client component).
- `app/admin/page.tsx` — admin login + dashboard.
- `lib/api.ts` — the only place that calls the backend (`NEXT_PUBLIC_API_BASE_URL`). Add new
  endpoints here rather than calling `fetch` directly from a component.
- `lib/device.ts` — anonymous per-browser device id (localStorage). Never log it or send it
  anywhere but this app's own API.
- `components/PdfViewer.tsx` — wraps `react-pdf`/`pdfjs-dist`. This touches browser-only
  globals (`DOMMatrix`, canvas) at import time, so it must always be loaded via
  `next/dynamic(..., { ssr: false })` from `app/page.tsx` — importing it directly breaks
  `next build`'s static prerender.

## Constraints

- Don't send the device id in a header or query string — it goes in the JSON body only (see
  `lib/api.ts`), matching the backend's "never a header/URL" expectation for anonymous ids.
- Don't add a build-time dependency beyond what's in `package.json`'s CDN-free set; this app
  is meant to build on Vercel's default Next.js pipeline with no extra config.

## Tests

```
npm test -- --run   # vitest
npm run build        # production build; also type-checks (tests/ is excluded, see tsconfig.json)
```
