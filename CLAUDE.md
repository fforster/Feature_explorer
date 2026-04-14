# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`feature_explorer.html` — a single-file browser tool that visualizes ALeRCE broker object features via an interactive pair plot, light curve, and sky view.

## Architecture

Everything lives in one self-contained HTML file with no build step. Load it directly in a browser.

### Layout (three-column, resizable)

```
[ Left sidebar 300px ] [ Main – pair plot, flex:1 ] [resizer] [ Right panel ~380px ]
                                                               [ LC chart (top 50%)  ]
                                                               [ Aladin sky (bot 50%)]
```

The boundary between the pair plot and the right panel is draggable via `#resizer` (5px strip). Dragging calls `Plotly.Plots.resize` on the pair plot during and after the drag.

### Key components and their IDs

| Component | Element ID | Library |
|---|---|---|
| Survey toggle | `#btn-lsst` / `#btn-ztf` | — |
| Classifier dropdown | `#sel-classifier` | — |
| Class tag multi-select | `#class-tags` / `#sel-class` | — |
| Feature search box | `#feat-search` | — |
| Feature checkbox list | `#feature-list` | — |
| Pair plot | `#pair-plot` | Plotly.js manual grid |
| Light curve | `#lc-div` | Plotly.js scatter |
| Sky view | `#aladin-lite-div` | Aladin Lite v3 |
| Share button | `#btn-share` | — |
| Resizer | `#resizer` | — |

### ALeRCE API endpoints (per survey)

**ZTF** (default survey)
- Classifiers: `https://api.alerce.online/ztf/v1/classifiers`
- Objects: `https://api.alerce.online/ztf/v1/objects?{params}`
  - ZTF uses `class` (not `class_name`) and requires `ranking=1`
- Features: `https://api.alerce.online/ztf/v1/objects/{oid}/features`
  - Returns `[{name, value, fid}]` — fid 0=global, 1=g, 2=r, 3=i
- Light curve v1: `https://api.alerce.online/ztf/v1/objects/{oid}/lightcurve`
- Light curve v2: `https://api.alerce.online/v2/lightcurve/lightcurve/{oid}?survey_id=ztf`
  - v2 is fetched in parallel with v1 to obtain `mag_corr`/`e_mag_corr` for science flux/mag

**LSST**
- Classifiers: `https://api-lsst.alerce.online/classifier_api/classifiers`
- Objects: `https://api-lsst.alerce.online/object_api/list_objects?survey_id=lsst&{params}`
- Features: `https://api-lsst.alerce.online/feature_api/features?survey_id=lsst&oid={oid}`
- Light curve: `https://api-lsst.alerce.online/lightcurve_api/lightcurve?survey_id=lsst&oid={oid}`

### Data flow

1. `init()` → reads URL hash; if valid state, sets `pendingRestore` and calls `fetchClassifiers()`; otherwise calls `fetchClassifiers()` directly
2. `fetchClassifiers()` → populates `#sel-classifier` and `classifierClasses` map; if `pendingRestore`, applies classifier + classes + query params and calls `runQuery()`
3. `onClassifierChange()` → populates `#sel-class`
4. `runQuery()` → fetches object list for each selected class, merges, optionally shuffles and samples N; calls `fetchAllFeatures()`
5. `fetchAllFeatures(oids)` → fetches features in parallel batches of 10; `pivotFeatures()` flattens `[{name, value, fid}]` into `{name_band: value}` dicts; stored in `featuresData[oid]`
6. `buildFeatureListUI()` → renders checkboxes from `allFeatureNames`; if `pendingRestore`, applies feature selection, transforms, colors, then calls `buildPairPlot()` and optionally `onPointSelected()`
7. `buildPairPlot()` → builds a manual lower-triangular grid of Plotly subplots; KDE fills on diagonal, scatter off-diagonal
8. `onPointSelected(idx)` → calls `highlightPoints([idx])`, then `loadObjectDetail()`
9. `loadObjectDetail(obj)` → fetches LC v1 and (ZTF only) v2 in parallel; cross-matches v2 detections by `candid` to copy `mag_corr`/`e_mag_corr`; normalizes via `normalizeDet()`; renders LC; calls `updateAladin()`
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
| `scatterTraceIdxs` | number[] | Plotly trace indices for multi-trace `selectedpoints` |
| `lcFluxMode` | bool | `false`=magnitude, `true`=flux (nJy) |
| `useScienceFlux` | bool | `false`=difference image, `true`=science/corrected image |
| `lcFoldMode` | bool | Phase-fold light curve by `Multiband_period_fid12` |
| `currentDetections` | array | Cached normalized detections for selected object |
| `pendingRestore` | object\|null | Decoded URL state waiting to be applied |
| `aladinInstance` / `aladinCat` | Aladin objects | Reused across selections |
| `selectedIdx` | number | Index into `objectsData` of highlighted point |

### Feature normalization (`pivotFeatures`)

ZTF band suffixes: fid 0 → `""`, 1 → `"_g"`, 2 → `"_r"`, 3 → `"_i"`  
Handles three response formats: bare array `[{name, value, fid}]`, wrapped `{features: [...]}`, and dict `{name: value}`.

### Detection normalization (`normalizeDet`)

Unifies field names across ZTF and LSST and computes flux fields:
- `mjd`: `mjd` → `midpointMjdTai` → `midPointTai`
- `mag` / `e_mag`: difference-image magnitude — `mag` → `psf_mag` → `magpsf` (never `mag_corr`)
- `band_name`: `band` field (LSST) or `fidMap[fid]` (ZTF)
- `psfFlux` / `psfFluxErr`: difference flux (nJy) — from API if present, else derived from `mag`
- `scienceFlux` / `scienceFluxErr`: science (corrected) flux — from `mag_corr`/`e_mag_corr` when `e_mag_corr > 0 && e_mag_corr < 1.0`; `e_mag_corr = 100.0` is ALeRCE's unreliable-correction sentinel

### Light curve display modes

Four combinations of two independent toggles:

| | Diff | Sci |
|---|---|---|
| **Mag** | `mag` / `e_mag` | `mag_corr` / `e_mag_corr` |
| **Flux** | `psfFlux` / `psfFluxErr` | `scienceFlux` / `scienceFluxErr` |

Science magnitude mode applies the same `e_mag_corr < 1.0` validity filter as science flux mode to exclude unreliable corrections.

Phase folding (ZTF): uses `Multiband_period_fid12` from `featuresData`; phase = `(((mjd - t0) % P) + P) % P / P`; two cycles shown by appending each point at `phase + 1`.

### Pair plot architecture

Plotly's `splom` trace was abandoned because it doesn't support custom diagonal cells. Instead, a manual lower-triangular grid is built using independent `xaxis{i}` / `yaxis{i}` pairs placed via fractional `domain` arrays:
- Off-diagonal cells: one scatter trace per class, pushed to `scatterTraceIdxs`
- Diagonal cells: one KDE fill trace per class (`gaussianKDE` with Silverman's bandwidth)
- `highlightPoints(idxs)` calls `Plotly.restyle(div, {selectedpoints: sp}, scatterTraceIdxs)` to highlight across all subplots simultaneously

### URL state sharing

`captureState()` serializes: survey, classifier, classes, selected features, transforms, query params (prob, ndet, sample size), custom colors, selected OID, and LC display state → JSON → `btoa(encodeURIComponent(...))` → `location.hash`.

`shareState()` (share button `#btn-share`) encodes current state into the hash and copies the full URL to clipboard.

`init()` on load reads the hash and sets `pendingRestore`; the restore is applied in two phases:
1. After `fetchClassifiers()` — classifier, classes, query params → `runQuery()`
2. After `buildFeatureListUI()` — feature checkboxes, transforms, colors → `buildPairPlot()` → `onPointSelected()` with LC state pre-applied

### Feature list search

`filterFeatureList(query)` hides/shows `.feature-item` rows by substring match on `input.value`. Called via `oninput` on `#feat-search`. Does not affect checkbox state of hidden rows.

### Aladin Lite v3

Loaded asynchronously from `aladin.cds.unistra.fr`. `updateAladin()` polls for `A.init` up to 8 seconds before giving up gracefully. The instance is created once and reused; `aladinCat.removeAll()` clears the previous marker before adding the new one.

## External dependencies (CDN, no install)

- Plotly.js 2.27 — pair plot and light curve
- Font Awesome 6.5 — icons
- Aladin Lite v3 — sky view (async load)

## Reference

See `../ALeRCE_explorer/alerce_explorer.html` for more advanced ALeRCE API usage patterns (ZTF/LSST field-name quirks, forced photometry, E(B-V) fetching, HiPS survey probing, spec-z overlays).
