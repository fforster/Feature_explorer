# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`feature_explorer.html` — a single-file browser tool that visualizes ALeRCE broker object features via an interactive pair plot, light curve, and sky view.

## Architecture

Everything lives in one self-contained HTML file with no build step. Load it directly in a browser.

### Layout (three-column, resizable)

```
[ Left sidebar (resizable, default 440px) ] [sidebar-resizer] [ Main – pair plot or UMAP, flex:1 ] [resizer] [ Right panel ~380px ]
                                                                                                             [ LC chart (top 50%)  ]
                                                                                                             [ Aladin sky (bot 50%)]
```

Two draggable dividers:
- `#sidebar-resizer` (5px strip) — between the sidebar and the main view. Dragging sets `sidebar.style.width` and resizes the active plot.
- `#resizer` (5px strip) — between the main view and the right panel. Dragging resizes the active plot during and after the drag.

The main column has a view-tab bar (`.view-tabs`) with `#btn-view-pairplot` / `#btn-view-umap`. Only one of `#pair-plot` or `#umap-plot` is visible at a time (see `switchView()`); each has its own placeholder (`#pair-plot-placeholder` / `#umap-placeholder`) shown when the plot has not yet been built.

### Key components and their IDs

| Component | Element ID | Library |
|---|---|---|
| Survey toggle | `#btn-lsst` / `#btn-ztf` | — |
| Classifier dropdown | `#sel-classifier` | — |
| Class tag multi-select | `#class-tags` / `#sel-class` | — |
| Feature search box | `#feat-search` | — |
| Feature list | `#feature-list` | — |
| Show Selected button | `#btn-show-selected` | — |
| Sample CSV download | `#btn-download-sample` | — |
| Data table button | `#btn-data-table` | — |
| UMAP params | `#umap-n-neighbors` / `#umap-min-dist` / `#umap-impute` / `#umap-impute-val` | — |
| View tabs | `#btn-view-pairplot` / `#btn-view-umap` | — |
| Pair plot | `#pair-plot` (+ `#pair-plot-placeholder`) | Plotly.js manual grid |
| UMAP plot | `#umap-plot` (+ `#umap-placeholder`) | Plotly.js scatter + umap-js |
| Plot toolbar | `.plot-toolbar` (`#btn-box` / `#btn-lasso` / `#btn-help`) | — |
| Help panel | `#help-panel` | — |
| Light curve | `#lc-div` (+ `#lc-spinner` overlay, `#lc-wrap`) | Plotly.js scatter |
| LC display toggles | `#lc-btn-mag` / `#lc-btn-flux` / `#lc-btn-sci` / `#lc-btn-fold` | — |
| LC overlay selector | `#lc-overlay-sel` | — |
| LC overlay info bar | `#lc-spm-info` | — |
| LC CSV download | `#btn-download-lc` | — |
| Sky view | `#aladin-lite-div` | Aladin Lite v3 |
| Data table modal | `#dt-modal` / `#dt-body` / `#dt-info` | — |
| Share button | `#btn-share` | — |
| Live indicator | `#live-indicator` / `#live-label` | — |
| Build timestamp | `#build-ts` | — |
| Sidebar resizer | `#sidebar-resizer` | — |
| Main/right resizer | `#resizer` | — |

### ALeRCE API endpoints (per survey)

**ZTF** (default survey)
- Classifiers: `https://api.alerce.online/ztf/v1/classifiers`
- Objects: `https://api.alerce.online/ztf/v1/objects?{params}`
  - ZTF uses `class` (not `class_name`) and requires `ranking=1`
  - Minimum detections parameter is `ndet` (not `n_det`)
- Features: `https://api.alerce.online/ztf/v1/objects/{oid}/features`
  - Returns `[{name, value, fid}]` — fid 0=global, 1=g, 2=r, 3=i
- Light curve v1: `https://api.alerce.online/ztf/v1/objects/{oid}/lightcurve`
- Light curve v2: `https://api.alerce.online/v2/lightcurve/lightcurve/{oid}?survey_id=ztf`
  - v2 is fetched in parallel with v1 to obtain `mag_corr`/`e_mag_corr` for science flux/mag

**LSST**
- Classifiers: `https://api-lsst.alerce.online/classifier_api/classifiers`
- Objects: `https://api-lsst.alerce.online/object_api/list_objects?survey_id=lsst&{params}`
  - Minimum detections parameter is `n_det`
- Features: `https://api-lsst.alerce.online/feature_api/features?survey_id=lsst&oid={oid}`
- Light curve: `https://api-lsst.alerce.online/lightcurve_api/lightcurve?survey_id=lsst&oid={oid}`

**Health check** — `checkApiConnection()` pings the classifiers endpoint for the active survey on load and every 60 s. Updates `#live-indicator` (pulsing red = live, grey static = offline).

### Data flow

1. `init()` → reads URL hash; if valid state, sets `pendingRestore` and calls `fetchClassifiers()`; otherwise calls `fetchClassifiers()` directly
2. `fetchClassifiers()` → populates `#sel-classifier` and `classifierClasses` map; if `pendingRestore`, applies classifier + classes + query params and calls `runQuery()`
3. `onClassifierChange()` → populates `#sel-class`
4. `runQuery()` → fetches object list for each selected class, merges, optionally shuffles and samples N; calls `fetchAllFeatures()`
5. `fetchAllFeatures(oids)` → fetches features in parallel batches of 10; `pivotFeatures()` flattens `[{name, value, fid}]` into `{name_band: value}` dicts; stored in `featuresData[oid]`
6. `buildFeatureListUI()` → renders feature rows from `allFeatureNames`; if `pendingRestore`, applies feature show state, transforms, colors, then calls `buildPairPlot()` and optionally `onPointSelected()`
7. `buildPairPlot()` → applies `featureFilters`, builds `plotObjIdx` mapping, then builds a manual lower-triangular grid of Plotly subplots; KDE fills on diagonal, scatter off-diagonal. Alternative: `buildUmapPlot()` → runs `_runUmap()` for a 2D UMAP embedding.
8. `onPointSelected(idx, fromView)` → cross-highlights in the non-originating view via `highlightPoints()` / `highlightUmapPoint()`, updates `#selected-info`, then `loadObjectDetail()`
9. `loadObjectDetail(obj)` → fetches LC v1 and (ZTF only) v2 in parallel; cross-matches v2 detections by `candid` to copy `mag_corr`/`e_mag_corr`; extracts forced-photometry earliest-MJD per band into `forcedPhotMjds` (for FLEET anchor); normalizes via `normalizeDet()`; renders LC; calls `updateAladin()`
10. `updateAladin(ra, dec, oid)` → lazy-initializes Aladin Lite; reuses instance via `aladinInstance.gotoRaDec()`

### State variables

| Variable | Type | Purpose |
|---|---|---|
| `currentSurvey` | string | `'ztf'` (default) or `'lsst'` |
| `objectsData` | array | Object metadata from list endpoint |
| `featuresData` | `{oid: {name: value}}` | Pivoted feature values |
| `selectedClasses` | string[] | Currently added classes |
| `classColorMap` | `{class: hex}` | Color per class for plot |
| `allFeatureNames` | string[] | Union of all feature keys |
| `featureTransforms` | `{name: 'log'\|'asinh'\|null}` | Per-feature axis transform |
| `featureFilters` | `{name: {min, max}}` | Per-feature value range filter applied before building the pair plot |
| `plotObjIdx` | number[]\|null | Maps plot-space Plotly point index → `objectsData` global index; `null` = identity (no filter active) |
| `showOnlySelected` | bool | When true, feature list shows only rows whose checkbox is checked |
| `scatterTraceIdxs` | number[] | Plotly trace indices for multi-trace `selectedpoints` |
| `lcFluxMode` | bool | `false`=magnitude, `true`=flux (µJy) |
| `useScienceFlux` | bool | `false`=difference image, `true`=science/corrected image |
| `lcFoldMode` | bool | Phase-fold light curve by `Multiband_period_fid12` |
| `lcOverlay` | string\|null | Active parametric overlay: `null`, `'spm'`, `'fleet'`, or `'tde_tail'` |
| `currentDetections` | array | Cached normalized detections for selected object |
| `forcedPhotMjds` | `{band: mjd}` | Earliest forced-photometry MJD per band (flux > 1 µJy) — anchors FLEET per-band time reference |
| `pendingRestore` | object\|null | Decoded URL state waiting to be applied |
| `aladinInstance` / `aladinCat` | Aladin objects | Reused across selections |
| `selectedIdx` | number | Index into `objectsData` of highlighted point |
| `activeView` | string | `'pairplot'` or `'umap'` — which main-column plot is visible |
| `umapScatterTraceIdx` | number\|null | Plotly trace index of the UMAP scatter (single trace) |
| `umapPlotObjIdx` | number[]\|null | Maps UMAP plot-space index → `objectsData` global index |
| `umapRunning` | bool | Guards against concurrent `buildUmapPlot()` invocations |

### Feature list UI

Each row in `#feature-list` has this structure (left to right):

```
[☐ checkbox] [👁 show-btn] [feature name] [log][asinh] [min][max]
```

- **Checkbox**: selection control for bulk operations (Select All / None / Default) and "Show Selected" filtering. Checking a feature automatically activates its Show button.
- **Show button** (`.show-btn`, eye icon): controls whether the feature is shown as a pair plot axis. `getSelectedFeatures()` reads active Show buttons — NOT checkboxes.
- **Feature name** (`.feat-name`): truncated with ellipsis. Must have `min-width: 0` for proper flex shrinking.
- **Transform buttons** (`.xform-btn`): `log` / `asinh` — toggle per-feature axis transform.
- **Min/max inputs** (`input.feat-filter`): filter objects by feature value range, applied in `buildPairPlot()`. Width is `36px`; use `input.feat-filter` selector (not `.feat-filter`) to override the global `input[type="number"] { width: 100% }` rule.

**Show Selected** (`#btn-show-selected`, `toggleShowSelected()`): toggles `showOnlySelected`; when active, `filterFeatureList` hides rows whose checkbox is unchecked.

**Feature search** (`#feat-search`, `filterFeatureList(query)`): substring match by default; supports glob patterns (`*`, `?`) which are converted to anchored regex.

### Feature normalization (`pivotFeatures`)

ZTF band suffixes: fid 0 → `""`, 1 → `"_g"`, 2 → `"_r"`, 3 → `"_i"`  
Handles three response formats: bare array `[{name, value, fid}]`, wrapped `{features: [...]}`, and dict `{name: value}`.

### Detection normalization (`normalizeDet`)

Unifies field names across ZTF and LSST and computes flux fields:
- `mjd`: `mjd` → `midpointMjdTai` → `midPointTai`
- `mag` / `e_mag`: difference-image magnitude — `mag` → `psf_mag` → `magpsf` (never `mag_corr`)
- `band_name`: `band` field (LSST) or `fidMap[fid]` (ZTF)
- `psfFlux` / `psfFluxErr`: difference flux (µJy) — from API if present, else derived from `mag`
- `scienceFlux` / `scienceFluxErr`: science (corrected) flux — from `mag_corr`/`e_mag_corr` when `e_mag_corr > 0 && e_mag_corr < 1.0`; `e_mag_corr = 100.0` is ALeRCE's unreliable-correction sentinel

### Light curve display modes

Four combinations of two independent toggles:

| | Diff | Sci |
|---|---|---|
| **Mag** | `mag` / `e_mag` | `mag_corr` / `e_mag_corr` |
| **Flux** | `psfFlux` / `psfFluxErr` | `scienceFlux` / `scienceFluxErr` |

Science magnitude mode applies the same `e_mag_corr < 1.0` validity filter as science flux mode to exclude unreliable corrections.

Phase folding (ZTF): uses `Multiband_period_fid12` from `featuresData`; phase = `(((mjd - t0) % P) + P) % P / P`; two cycles shown by appending each point at `phase + 1`.

**Y-axis clipping (magnitude mode)**: if any trace value exceeds 27, the y-axis is clipped to `[27, yMin − 0.3]` (range is reversed since larger mag = fainter). Otherwise `autorange: 'reversed'` is used. This prevents overlay extrapolations from collapsing the scale.

### Parametric model overlays

Selected via `#lc-overlay-sel` dropdown. Active overlay is stored in `lcOverlay`. When an overlay is active, a parameter table is shown in `#lc-spm-info`. Overlays are not drawn in fold mode.

#### SPM (`lcOverlay === 'spm'`)

Model (Sánchez-Sáez+2021 Eq. A5):
```
F(t) = A × (1 − β^((t−t₀)/γ)) / (1 + exp(−(t−t₀)/τ_rise))  [rise]
     + A × (1 − β) × exp(−max(0, t−t₁)/τ_fall) / denom       [fall]
```
Smoothly blended at `t₁ = t₀ + γ` via a sigmoid.

- **Time**: `t = mjd − first_mjd_global` (global across all bands)
- **Units**: `SPM_A` is stored in mJy (extractor multiplied µJy observations by 0.001). Must multiply by 1000 (mJy → µJy) before display. `ABZP = 23.9`.
- **Parameters**: `SPM_A_{band}`, `SPM_beta_{band}`, `SPM_t0_{band}`, `SPM_gamma_{band}`, `SPM_tau_rise_{band}`, `SPM_tau_fall_{band}`, `SPM_chi_{band}`
- **Line style**: dashed

#### FLEET (`lcOverlay === 'fleet'`)

Model (fleet_model in tde_extractor.py):
```
mag(t_norm) = exp(w × (t_norm − t₀)) − a × w × (t_norm − t₀) + m₀
```

- **Time**: `t_norm = mjd − first_mjd_in_band` — per-band normalization. `first_mjd_in_band` is the earliest of (a) alert detections with `psfFlux > 1 µJy` and (b) forced-photometry points with `psfFlux > 1 µJy` (via `forcedPhotMjds`, populated in `loadObjectDetail` from the v2 `forced_photometry` key). This matches the extractor's reference, which forced-phot frequently pushes earlier than the first alert.
- **Units**: output is directly in magnitudes (fit was done on diff-image magnitudes); flux mode converts via `10^((23.9 − mag) / 2.5)`
- **Parameters**: `fleet_a_{band}`, `fleet_w_{band}`, `fleet_m0_{band}`, `fleet_t0_{band}`, `fleet_chi_{band}`
- **Line style**: dotted

#### TDE Tail (`lcOverlay === 'tde_tail'`)

Model (TDETailExtractor in tde_extractor.py) — linear in log-time, post-peak only:
```
mag(t) = TDE_mag0 + TDE_decay × 2.5 × log₁₀(t − t_peak + 40)
```

- **Time**: `t = mjd`, `t_peak` = MJD of the brightest (min mag) detection in the band — **derived from `currentDetections`** (not stored as a feature). Filtered to `e_mag < 1.0` and `mag < 30` matching the extractor.
- **Valid range**: `t > t_peak` only; grid starts at `t_peak`
- **Units**: output is in diff-image magnitudes; flux mode converts via `10^((23.9 − mag) / 2.5)`
- **Parameters**: `TDE_mag0_{band}`, `TDE_decay_{band}`, `TDE_decay_chi_{band}`
- **Line style**: dash-dot

### Pair plot architecture

Plotly's `splom` trace was abandoned because it doesn't support custom diagonal cells. Instead, a manual lower-triangular grid is built using independent `xaxis{i}` / `yaxis{i}` pairs placed via fractional `domain` arrays:
- Off-diagonal cells: one scatter trace per class, pushed to `scatterTraceIdxs`
- Diagonal cells: one KDE fill trace per class (`gaussianKDE` with Silverman's bandwidth)
- `highlightPoints(idxs)` calls `Plotly.restyle(div, {selectedpoints: sp}, scatterTraceIdxs)` to highlight across all subplots simultaneously

**Feature filtering**: before building, `buildPairPlot()` applies `featureFilters` to `objectsData`, producing `plotEntries` (a subset). `plotObjIdx = plotEntries.map(e => e.i)` maps Plotly point indices back to global `objectsData` indices. `onPointSelected` uses `plotObjIdx.indexOf(idx)` to find the correct Plotly point for highlighting.

**Placeholder / building state**: `#pair-plot` is hidden and `#pair-plot-placeholder` is shown before the first build. While `buildPairPlot()` runs, the placeholder switches to a spinning icon (`fa-spinner fa-spin`) with "Building pair plot…" text; on completion it is hidden and `#pair-plot` is shown.

### UMAP view

An alternative 2D embedding of the same feature set, shown in `#umap-plot` instead of the pair plot. Toggled via the view tabs (`switchView('umap')`).

- **Trigger**: `buildUmapPlot()` (via the "Run UMAP" button or the `#btn-view-umap` tab when already built). Guarded by `umapRunning` to prevent concurrent runs.
- **Library**: `umap-js@1.3.3` loaded on demand via `import('https://esm.sh/umap-js@1.3.3')` with a 15 s timeout; cached on `window._UMAP`.
- **Feature selection**: uses `getSelectedFeatures()` (same Show-button state as the pair plot); requires ≥ 2 features and ≥ 5 objects after filtering.
- **Filtering**: applies `featureFilters` the same way `buildPairPlot` does.
- **Transforms**: applies `featureTransforms` per feature before imputation.
- **Missing values**: imputed per column via `#umap-impute` — `mean` (default), `median`, or `value` (custom value from `#umap-impute-val`). `normalizeMatrix()` then z-scores each column.
- **Parameters**: `nNeighbors` (clamped to `nObjs - 1`) from `#umap-n-neighbors`; `minDist` from `#umap-min-dist`.
- **Fit**: `umapInstance.fitAsync(normalized, epoch => …)` reports progress every 10 epochs via `#umap-ph-text` and the status bar.
- **Output**: a single Plotly scatter trace colored by class (`classColorMap`) with `selectedpoints` highlight; `umapScatterTraceIdx = 0`, `umapPlotObjIdx` maps plot indices back to global `objectsData` indices.
- **Cross-highlight**: clicking or box/lasso-selecting in UMAP calls `onPointSelected(globalIdx, 'umap')`, which also calls `highlightPoints()` on the pair plot if it has been built. The inverse direction works the same way from the pair plot.

### Plot toolbar and help panel

Floating toolbar `.plot-toolbar` over the main column:
- `#btn-box` / `#btn-lasso` → `setDragMode('select'|'lasso')` applies `{dragmode}` to whichever of `#pair-plot` / `#umap-plot` is currently visible and has data.
- `#btn-help` → `toggleHelp()` shows `#help-panel` (static HTML describing selection, navigation, and plot layout).

### Data table modal

`#dt-modal` is a popup opened by `#btn-data-table` (`openDataTable()`). `renderDataTable()` renders a `<table class="dt">` with columns `[OID, Class, P, …selected features]`:
- **Sorting**: click a header to call `dtSort(col)` — toggles `dtSortAsc` on the same column, resets to ascending on a different column. `dtSortCol = null` → original `objectsData` order.
- **Row click**: OID links call `onPointSelected(i); closeDataTable()` to jump to the object.
- **Selected row**: the row whose global index matches `selectedIdx` is styled `.dt-selected` and scrolled into view.
- **CSV export**: `downloadDTCSV()` exports the current sort order (same columns as the visible table).
- Closed by clicking outside the panel, pressing Escape, or the close button.

### CSV downloads

All downloads go through `triggerDownload(content, filename)`; `nowStamp()` provides a UTC timestamp suffix (`YYYY-MM-DD_HHMMSS`).

- **`downloadSampleCSV()`** (`#btn-download-sample`) — full loaded sample: `oid, class_name, probability, meanra, meandec, …allFeatureNames`. Filename `alerce_sample_{classifier}_{stamp}.csv`.
- **`downloadLCCSV()`** (`#btn-download-lc`) — detections of the currently selected object. The selected overlay's per-band parameters are included as `# ` header comments above the CSV rows. Filename includes `{oid}` and `{stamp}`.
- **`downloadDTCSV()`** — subset table (selected features only) in current sort order.

### Loading states / spinners

- **Pair plot**: `#pair-plot-placeholder` shows a static icon before the first build; during `buildPairPlot()` it is swapped to `fa-spinner fa-spin` with "Building pair plot…" text.
- **UMAP**: `umapSetMsg(iconClass, msg)` updates the placeholder icon and text; during `fitAsync` the status bar and placeholder both report "Optimising… epoch N".
- **Light curve**: `#lc-spinner` is an overlay div positioned on top of `#lc-div` (inside `#lc-wrap`, which is `position: relative`). It must be an overlay — writing "Loading…" into the Plotly div itself breaks Plotly's internal state. Shown during `loadObjectDetail()` and hidden when the LC is rendered or an error occurs.

### URL state sharing

`captureState()` serializes: survey, classifier, classes, shown features (show button state), transforms, query params (prob, ndet, sample size), feature filters, custom colors, selected OID, and LC display state (flux mode, sci mode, fold mode, overlay) → JSON → `btoa(encodeURIComponent(...))` → `location.hash`. Query params (`prob`, `ndet`, `sample`, `n`) are captured from the `lastQuery*` globals that `runQuery()` snapshots, not from the input values at share time — this preserves the params that produced the current sample even after the inputs are edited.

`shareState()` (share button `#btn-share`) encodes current state into the hash and copies the full URL to clipboard.

`init()` on load reads the hash and sets `pendingRestore`; the restore is applied in two phases:
1. After `fetchClassifiers()` — classifier, classes, query params → `runQuery()`
2. After `buildFeatureListUI()` — feature show/checkbox state, transforms, colors, filters → `buildPairPlot()` → `onPointSelected()` with LC state pre-applied

### Build timestamp

`BUILD_TIME` constant (ISO 8601 UTC string) near the top of the `<script>` block. Displayed in the header via `#build-ts` as `build YYYY-MM-DD HH:MM UTC`. **Must be updated to the current time whenever the file is modified.**

### Aladin Lite v3

Loaded asynchronously from `aladin.cds.unistra.fr`. `updateAladin()` polls for `A.init` up to 8 seconds before giving up gracefully. The instance is created once and reused; `aladinCat.removeAll()` clears the previous marker before adding the new one.

## External dependencies (CDN, no install)

- Plotly.js 2.27 — pair plot, UMAP scatter, and light curve
- Font Awesome 6.5 — icons
- Aladin Lite v3 — sky view (async load)
- `umap-js@1.3.3` — loaded on demand via `esm.sh` when UMAP is first run

## CSS gotchas

- `input[type="number"] { width: 100%; }` is a global rule with specificity `0,1,1`. To override a width on a number input, use `input.my-class { width: Xpx; }` (specificity `0,2,1`), not `.my-class { width: Xpx; }` (specificity `0,1,0`).
- Flex items with `overflow: hidden` must also have `min-width: 0` to shrink properly below their natural content width.
- Auto margins (`margin-left: auto`) on a flex sibling consume free space before `flex-grow` items can expand — remove them if a `flex: 1` item isn't filling available space.

## Reference

See `../ALeRCE_explorer/alerce_explorer.html` for more advanced ALeRCE API usage patterns (ZTF/LSST field-name quirks, forced photometry, E(B-V) fetching, HiPS survey probing, spec-z overlays, live indicator pattern).
