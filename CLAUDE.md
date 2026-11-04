# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`feature_explorer.html` — a single-file browser tool that visualizes ALeRCE broker object features via an interactive pair plot, light curve, and sky view.

## Architecture

Everything lives in one self-contained HTML file with no build step. All data comes from the **ALeRCE multisurvey TAP service** (`https://tap.alerce.online/tap`, schema `alerce_tap`).

**Running it**: the TAP service does not send CORS headers yet, so opening the file directly (`file://`) shows a "TAP not reachable" message. Run `python3 tap_proxy.py` (stdlib only) and open `http://localhost:8765/feature_explorer.html`; the proxy serves this folder and forwards `/tap/*` to `tap.alerce.online`. Once the service sends `Access-Control-Allow-Origin`, the page talks to it directly. A different endpoint can be forced with `?tap=<url>`.

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
| Sampling mode | `#sel-sample` (`top` / `random`) + `#n-per-class` | — |
| Classifier dropdown | `#sel-classifier` | — |
| Class tag multi-select | `#class-tags` / `#sel-class` | — |
| Feature search box | `#feat-search` | — |
| Feature list | `#feature-list` | — |
| Feature version label | `#feat-version` | — |
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
| LC display toggles | `#lc-btn-mag` / `#lc-btn-flux` / `#lc-btn-sci` / `#lc-btn-fp` / `#lc-btn-fold` | — |
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

### Data source: ALeRCE TAP

**Client** (`tapQuery(adql)` → `[{col: 'string'}]`): form-encoded POST to `…/tap/sync` with `FORMAT=csv` (a CORS "simple request", no preflight). VOTable error documents are parsed into thrown `Error`s. Always CSV, never JSON: TAP's JSON encodes 64-bit oids as numbers and JS loses precision. `parseCSV()` is a small RFC 4180 parser; `num()` converts `''` → `null`.

**Endpoint resolution** (`resolveTapUrl()`): candidates are `?tap=` override → `TAP_DEFAULT_URL` → same-origin `./tap/sync` (the proxy). The first one answering a probe query wins and is remembered in `localStorage` (`featureExplorer.tapUrl`); on later loads it is used without probing, and `tapQuery` re-probes only if it fails with a network error. If nothing answers, `TapUnreachableError` carries the "run tap_proxy.py" message shown in the status bar.

**Identity**: an object is `(sid, oid)` — sid 0 = ZTF, 1 = LSST DIA object (`SURVEY_CONFIG[survey].sid`; classifiers are filtered by `tid`, 0 = ZTF, 1 = Rubin). ZTF oids are the idmapper master id `(1<<55) + year·26⁷ + base-26 letters`; `ztfOidToName()` / `ztfNameToOid()` convert (BigInt). `objectsData[i].oid` is the **display id** (ZTF name or LSST diaObjectId string) used everywhere in the UI, CSVs, `featuresData` keys and share URLs; `objectsData[i].dbOid` is the int64 string used in ADQL.

**Lookup tables** (`loadLookups()` → `LUT`): `classifier`, `taxonomy`, `feature_name_lut`, `feature_version_lut`, `band`, cached in `localStorage` (`featureExplorer.lut.v1`) for 12 h. Band ids: ZTF 1=g 2=r 3=i; LSST 1=g 2=r 3=i 4=z 5=y **6=u**. Helpers: `bandName(band)`, `surveyBands()`, `featureSuffix(band)`, `currentClassifier()`.

**Queries** (one per step, not one per object):

| Step | ADQL (sketch) |
|---|---|
| Sample (per class, parallel) | `SELECT TOP N p.oid, p.probability, o.meanra, o.meandec, o.n_det, o.firstmjd, o.lastmjd FROM probability p JOIN object o ON (oid, sid) WHERE p.sid, p.classifier_id, p.class_id, p.ranking = 1 [, p.probability >= …] [, o.n_det >= …]` + `ORDER BY p.probability DESC` (top) or `MOD(p.oid, K) = seed % K` with K = 97 → 13 → 1 until N rows (random) |
| Features (chunks of 500 oids) | `SELECT oid, feature_id, band, version, feature_value FROM feature WHERE sid = … AND oid IN (…)` |
| Class probability vector | `SELECT oid, class_id, classifier_version, probability FROM probability WHERE sid, classifier_id AND oid IN (…)` → `P_<class>` features |
| ZTF light curve | `detection ⋈ ztf_detection` (on oid + measurement_id), `forced_photometry ⋈ ztf_forced_photometry`, `ztf_non_detection` — 3 parallel queries |
| LSST light curve | `detection ⋈ lsst_detection`, `forced_photometry ⋈ lsst_forced_photometry` (on oid + measurement_id + sid) |

ADQL dialect notes: no `RAND()`, no scalar subqueries in `WHERE` (use joins). Server cost is ~1.7 s per query and it gains little from more than ~2 concurrent queries (`TAP_CONCURRENCY = 2`); splitting the feature query into smaller chunks is *slower*. Typical: 300 ZTF objects + 236 features ≈ 13 s; a light curve ≈ 2–4 s.

**Health check** — `checkApiConnection()` runs a one-row TAP query on load and every 60 s. Updates `#live-indicator` (pulsing red = live, grey static = offline).

### Data flow

1. `init()` → reads URL hash; if valid state, sets `pendingRestore` and calls `fetchClassifiers()`; otherwise calls `fetchClassifiers()` directly
2. `fetchClassifiers()` → `loadLookups()`, populates `#sel-classifier` (classifiers with the survey's `tid`, ordered by `SURVEY_CONFIG.priorities`) and `classifierClasses`; if `pendingRestore`, applies classifier + classes + query params and calls `runQuery()`
3. `onClassifierChange()` → populates `#sel-class`
4. `runQuery()` → one sample query per selected class (parallel), merges/dedupes by `dbOid`, then `fetchAllFeatures(objectsData, clf)`
5. `fetchAllFeatures()` → feature + probability-vector queries per 500-oid chunk; pivots long rows into `featuresData[oid][name + featureSuffix(band)]`; sets `allFeatureNames` and the `#feat-version` label (version name → number of objects)
6. `buildFeatureListUI()` → renders feature rows; default axes come from `computeDefaultFeatures()`; if `pendingRestore`, applies feature show state, transforms, colors, then calls `buildPairPlot()` and optionally `onPointSelected()`
7. `buildPairPlot()` → applies `featureFilters`, builds `plotObjIdx` mapping, then builds a manual lower-triangular grid of Plotly subplots; KDE fills on diagonal, scatter off-diagonal. Alternative: `buildUmapPlot()` → runs `_runUmap()` for a 2D UMAP embedding.
8. `onPointSelected(idx, fromView)` → cross-highlights in the non-originating view via `highlightPoints()` / `highlightUmapPoint()`, updates `#selected-info`, then `loadObjectDetail()`
9. `loadObjectDetail(obj)` → `updateAladin()`, then `fetchLightCurve(obj)` (TAP); normalizes rows with `ztfPoint()` / `lsstPoint()` into `currentDetections` (kinds `det` and `fp`) and `currentNonDets`; renders LC. `lcLoadToken` discards responses superseded by a newer click.
10. `updateAladin(ra, dec, oid)` → lazy-initializes Aladin Lite; reuses instance via `aladinInstance.gotoRaDec()`

### State variables

| Variable | Type | Purpose |
|---|---|---|
| `currentSurvey` | string | `'ztf'` (default) or `'lsst'` |
| `LUT` | object | Lookup tables (classifiers, classes per classifier, feature names/versions, bands per sid) |
| `objectsData` | array | `{oid (display), dbOid, sid, class_name, probability, meanra, meandec, n_det, firstmjd, lastmjd}` |
| `featuresData` | `{oid: {name: value}}` | Pivoted feature values (keyed by display oid) |
| `selectedClasses` | string[] | Currently added classes |
| `classColorMap` | `{class: hex}` | Color per class for plot |
| `allFeatureNames` | string[] | Union of all feature keys (incl. `P_<class>`) |
| `featureTransforms` | `{name: 'log'\|'asinh'\|null}` | Per-feature axis transform |
| `featureFilters` | `{name: {min, max}}` | Per-feature value range filter applied before building the pair plot |
| `plotObjIdx` | number[]\|null | Maps plot-space Plotly point index → `objectsData` global index; `null` = identity (no filter active) |
| `showOnlySelected` | bool | When true, feature list shows only rows whose checkbox is checked |
| `scatterTraceIdxs` | number[] | Plotly trace indices for multi-trace `selectedpoints` |
| `lcFluxMode` | bool | `false`=magnitude, `true`=flux (µJy) |
| `useScienceFlux` | bool | `false`=difference image, `true`=science/corrected image |
| `lcFoldMode` | bool | Phase-fold light curve by `Multiband_period` |
| `lcShowFP` | bool | Show forced photometry and ZTF upper limits (`#lc-btn-fp`) |
| `lcOverlay` | string\|null | Active parametric overlay: `null`, `'spm'`, `'fleet'`, `'tde_tail'` or `'ulens'` |
| `currentDetections` | array | Normalized LC points (`kind: 'det' \| 'fp'`) for the selected object |
| `currentNonDets` | array | ZTF upper limits `{mjd, band_name, diffmaglim}` |
| `lcLoadToken` | number | Incremented per LC load; stale responses are dropped |
| `lastQuery*` | strings | `Prob`, `Ndet`, `N`, `Sample`, `Seed` — params that produced the current sample (for share URLs) |
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

### Feature naming (`fetchAllFeatures`)

`alerce_tap.feature` is long format (`oid, sid, feature_id, band, version, feature_value`) and keeps only the **latest** value per object and feature, so there is no version selector; `#feat-version` shows which extractor versions the sample contains (LSST samples often mix versions). Names come from `feature_name_lut` (per sid). Band suffix via `featureSuffix(band)`: `0` → `""`, single band → `_g`, `_r`, …, multi-digit band sets → concatenated letters (`12` → `_gr`, `23` → `_ri`, `61` → `_ug`). The active classifier's full probability vector is added as `P_<class>`.

**Default axes** (`computeDefaultFeatures()`): the first `DEFAULT_FEATURE_MAX` names of `DEFAULT_FEATURE_PREFS` populated for ≥ 50 % of the sample (many variability features exist only for a subset of objects), topped up to 3 with the best-covered features (excluding `*_mjd_ref`, `Coordinate_*`, `P_*`).

### Light curve points (`ztfPoint` / `lsstPoint`)

Each point: `{kind: 'det'|'fp', mjd, band_name, mag, e_mag, psfFlux, psfFluxErr, mag_corr, e_mag_corr, scienceFlux, scienceFluxErr}` (fluxes in µJy, `ABZP = 23.9`).
- **ZTF** (magnitudes): detections use `magpsf`/`sigmapsf`, forced photometry `mag`/`e_mag`; `psfFlux = sign(isdiffpos) × 10^((23.9 − mag)/2.5)`. Forced-phot points only get a `mag` when the flux is positive. Science values from `magpsf_corr`/`sigmapsf_corr` (detections) or `mag_corr`/`e_mag_corr` (forced phot), kept only when `0 < e_mag_corr < 1` (`100` is ALeRCE's unreliable-correction sentinel).
- **LSST** (fluxes in **nJy** → ÷1000): `psfflux`/`psffluxerr` (difference) and `scienceflux`/`sciencefluxerr` (science); magnitudes derived where flux > 0.
- **Upper limits** (ZTF only): `ztf_non_detection.diffmaglim`, drawn as faint down-triangles in unfolded magnitude mode.

### Light curve display modes

Four combinations of two independent toggles:

| | Diff | Sci |
|---|---|---|
| **Mag** | `mag` / `e_mag` | `mag_corr` / `e_mag_corr` |
| **Flux** | `psfFlux` / `psfFluxErr` | `scienceFlux` / `scienceFluxErr` |

Science magnitude mode applies the same `e_mag_corr < 1.0` validity filter as science flux mode to exclude unreliable corrections. In magnitude mode forced-photometry points are shown only at ≥ 3σ (`e_mag < 0.36`); flux mode shows them all. One Plotly trace per (band, kind): detections filled, forced photometry open circles (`lcPointValue()` decides what is plottable).

Phase folding: uses `Multiband_period_gr` (ZTF) or `Multiband_period` (LSST, band 0) via `getCurrentPeriod()`; phase = `(((mjd - t0) % P) + P) % P / P`; two cycles shown by appending each point at `phase + 1`.

**Y-axis clipping (magnitude mode)**: if any trace value exceeds 27, the y-axis is clipped to `[27, yMin − 0.3]` (range is reversed since larger mag = fainter). Otherwise `autorange: 'reversed'` is used. This prevents overlay extrapolations from collapsing the scale.

### Parametric model overlays

Selected via `#lc-overlay-sel` dropdown. Active overlay is stored in `lcOverlay`. Definitions (label, line dash, parameter table) live in `OVERLAY_DEFS`; `overlayValue()` evaluates a model, `computeOverlayTraces()` draws one 200-point line per survey band over the plotted MJD range. When an overlay is active, a parameter table is shown in `#lc-spm-info` (bands without parameters are omitted). Overlays are not drawn in fold mode.

**Time references are stored as features** (checked against the photometry to ≤ 0.005 d; `overlayRefs()`): `SPM_mjd_ref` (first observation, any band), `fleet_mjd_ref_{band}` (first point with flux > 1 µJy, incl. forced phot), `TDE_mjd_ref_{band}` (brightest point incl. forced phot), `ulens_mjd_ref` (first point with e_mag < 1). Older feature versions (some LSST objects) lack them, so each falls back to the same quantity derived from `currentDetections` (detections + forced photometry).

#### SPM (`lcOverlay === 'spm'`)

Model (Sánchez-Sáez+2021 Eq. A5):
```
F(t) = A × (1 − β^((t−t₀)/γ)) / (1 + exp(−(t−t₀)/τ_rise))  [rise]
     + A × (1 − β) × exp(−max(0, t−t₁)/τ_fall) / denom       [fall]
```
Smoothly blended at `t₁ = t₀ + γ` via a sigmoid.

- **Time**: `t = mjd − SPM_mjd_ref`
- **Units**: `SPM_A` is stored in mJy for both ZTF and LSST (extractor multiplied µJy observations by 0.001; checked against LSST peak fluxes). Must multiply by 1000 (mJy → µJy) before display. `ABZP = 23.9`.
- **Parameters**: `SPM_A_{band}`, `SPM_beta_{band}`, `SPM_t0_{band}`, `SPM_gamma_{band}`, `SPM_tau_rise_{band}`, `SPM_tau_fall_{band}`, `SPM_chi_{band}`
- **Line style**: dashed

#### FLEET (`lcOverlay === 'fleet'`)

Model (fleet_model in tde_extractor.py):
```
mag(t_norm) = exp(w × (t_norm − t₀)) − a × w × (t_norm − t₀) + m₀
```

- **Time**: `t_norm = mjd − fleet_mjd_ref_{band}` (per-band reference)
- **Units**: output is directly in magnitudes (fit was done on diff-image magnitudes); flux mode converts via `10^((23.9 − mag) / 2.5)`
- **Parameters**: `fleet_a_{band}`, `fleet_w_{band}`, `fleet_m0_{band}`, `fleet_t0_{band}`, `fleet_chi_{band}`
- **Line style**: dotted

#### TDE Tail (`lcOverlay === 'tde_tail'`)

Model (TDETailExtractor in tde_extractor.py) — linear in log-time, post-peak only:
```
mag(t) = TDE_mag0 + TDE_decay × 2.5 × log₁₀(t − t_peak + 40)
```

- **Time**: `t = mjd`, `t_peak = TDE_mjd_ref_{band}` (brightest point in the band, forced photometry included)
- **Valid range**: `t > t_peak` only; grid starts at `t_peak`
- **Units**: output is in diff-image magnitudes; flux mode converts via `10^((23.9 − mag) / 2.5)`
- **Parameters**: `TDE_mag0_{band}`, `TDE_decay_{band}`, `TDE_decay_chi_{band}`
- **Line style**: dash-dot

#### Microlensing (`lcOverlay === 'ulens'`)

Model (ulens_extractor.py) — point-lens magnification with blending, in magnitudes:
```
u(t) = √(u₀² + ((t − t₀)/t_E)²),  A = (u² + 2) / (u √(u² + 4))
mag(t) = m₀ − 2.5 log₁₀(f_s (A − 1) + 1)
```

- **Time**: `t = mjd − ulens_mjd_ref`
- **Parameters**: `ulens_u0_{band}`, `ulens_tE_{band}`, `ulens_fs_{band}`, `ulens_t0_{band}`, `ulens_mag0_{band}`, `ulens_chi_{band}`
- **Line style**: long dash

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

- **`downloadSampleCSV()`** (`#btn-download-sample`) — full loaded sample: `oid, alerce_oid, sid, class_name, probability, meanra, meandec, n_det, …allFeatureNames` (names containing `/` etc. are CSV-quoted). Filename `alerce_sample_{classifier}_{stamp}.csv`.
- **`downloadLCCSV()`** (`#btn-download-lc`) — detections, forced photometry (`kind=fp`) and ZTF upper limits (`kind=upper_limit`, `mag` = diffmaglim) of the selected object. Metadata, period, and every overlay's per-band parameters plus `*_mjd_ref` times are included as `# ` header comments. Filename includes `{oid}` and `{stamp}`.
- **`downloadDTCSV()`** — subset table (selected features only) in current sort order.

### Loading states / spinners

- **Pair plot**: `#pair-plot-placeholder` shows a static icon before the first build; during `buildPairPlot()` it is swapped to `fa-spinner fa-spin` with "Building pair plot…" text.
- **UMAP**: `umapSetMsg(iconClass, msg)` updates the placeholder icon and text; during `fitAsync` the status bar and placeholder both report "Optimising… epoch N".
- **Light curve**: `#lc-spinner` is an overlay div positioned on top of `#lc-div` (inside `#lc-wrap`, which is `position: relative`). It must be an overlay — writing "Loading…" into the Plotly div itself breaks Plotly's internal state. Shown during `loadObjectDetail()` and hidden when the LC is rendered or an error occurs.

### URL state sharing

`captureState()` serializes: survey, classifier, classes, shown features (show button state), transforms, query params (prob, ndet, sample size, sampling mode `smp` + hash `seed` for random samples), feature filters, custom colors, selected OID (display id), and LC display state (flux mode, sci mode, fold mode, `lcFp`, overlay) → JSON → `btoa(encodeURIComponent(...))` → `location.hash`. Query params (`prob`, `ndet`, `sample`, `n`) are captured from the `lastQuery*` globals that `runQuery()` snapshots, not from the input values at share time — this preserves the params that produced the current sample even after the inputs are edited.

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
- ALeRCE TAP (`tap.alerce.online`) — all data; `tap_proxy.py` (Python stdlib) until the service sends CORS headers

## CSS gotchas

- `input[type="number"] { width: 100%; }` is a global rule with specificity `0,1,1`. To override a width on a number input, use `input.my-class { width: Xpx; }` (specificity `0,2,1`), not `.my-class { width: Xpx; }` (specificity `0,1,0`).
- Flex items with `overflow: hidden` must also have `min-width: 0` to shrink properly below their natural content width.
- Auto margins (`margin-left: auto`) on a flex sibling consume free space before `flex-grow` items can expand — remove them if a `flex: 1` item isn't filling available space.

## Reference

TAP schema reference: `../alerce-book/07-database.md` and the browsable `https://tap.alerce.online/browse/alerce_tap/multisurvey_lowercase`. See `../ALeRCE_explorer/alerce_explorer.html` for older REST API usage patterns (ZTF/LSST field-name quirks, forced photometry, E(B-V) fetching, HiPS survey probing, spec-z overlays, live indicator pattern).
