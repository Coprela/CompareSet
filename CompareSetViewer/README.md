# CompareSet Viewer PCF

This project contains the CompareSet PDF comparison engine implemented as a Power Apps Component Framework (PCF) control. The control accepts two PDF revisions as Base64 strings, performs a page-by-page visual comparison, and returns a marked-up PDF plus structured metadata describing the detected differences.

## Getting started

```bash
npm install
npm start -- --https
npm run build
```

The build command produces the importable solution at `out/CompareSetViewer/CompareSetViewer_1_0_0.zip`.

## Local validation checklist

1. Run `npm start -- --https` and open the PCF test harness that launches automatically.
2. Provide Base64 strings (or uploaded files, if enabled in the harness) for `oldPdfBase64` and `newPdfBase64`.
3. Toggle `runCompare` to **true** to initiate processing.
4. Confirm that `status`, `diffSummaryJson`, `diffCount`, and `outputPdfBase64` populate without manifest validation errors.
5. Decode `outputPdfBase64` to confirm that the generated PDF preserves vector content with red overlays on the old page and green overlays on the new page.

## Project layout

```
CompareSetViewer/
  ├─ ControlManifest.Input.xml
  ├─ package.json
  ├─ tsconfig.json
  ├─ src/
  │   ├─ index.ts         # PCF entry point and property binding
  │   ├─ compare.ts       # Comparison pipeline orchestrator
  │   ├─ renderPdf.ts     # pdfjs rendering helpers
  │   ├─ diff.ts          # Image differencing, morphology, connected components
  │   ├─ regions.ts       # Region classification and grid labeling
  │   ├─ overlayPdf.ts    # PDF overlay writer using pdf-lib
  │   ├─ coords.ts        # Coordinate transform helpers
  │   ├─ types.ts         # Shared interfaces
  │   └─ worker/compareWorker.ts
  ├─ strings/
  │   └─ Strings.resx
  └─ README.md
```

The control streams status updates via the `status` output and exposes the generated diff PDF, summary JSON, and total region count as bound outputs.
