# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`feature_explorer.html` — a single-file browser tool that visualizes ALeRCE broker object features via an interactive pair plot, light curve, and sky view.

## Architecture

Everything lives in one self-contained HTML file with no build step. Load it directly in a browser.

### Layout (three-column)

```
[ Left sidebar 300px ] [ Main – Plotly splom ] [ Right panel 380px ]
                                                [ LC chart (top 50%) ]
                                                [ Aladin sky (bot 50%)]
```

### Key components and their IDs

| Component | Element ID | Library |
|---|---|---|
| Survey toggle | `#btn-lsst` / `#btn-ztf` | — |
| Classifier dropdown | `#sel-classifier` | — |
| Class tag multi-select | `#class-tags` / `#sel-class` | — |
| Feature checkbox list | `#feature-list` | — |
| Pair plot | `#pair-plot` | Plotly.js splom trace |
| Light curve | `#lc-div` | Plotly.js scatter |
| Sky view | `#aladin-lite-div` | Aladin Lite v3 |

### ALeRCE API endpoints (per survey)

**ZTF**
- Classifiers: `https://api.alerce.online/ztf/v1/classifiers`
- Objects: `https://api.alerce.online/ztf/v1/objects?{params}`
  - ZTF uses `class` (not `class_name`) and requires `ranking=1`
- Features: `https://api.alerce.online/ztf/v1/objects/{oid}/features`
  - Returns `[{name, value, fid}]` — fid 0=global, 1=g, 2=r, 3=i
- Light curve: `https://api.alerce.online/ztf/v1/objects/{oid}/lightcurve`

**LSST**
- Classifiers: `https://api-lsst.alerce.online/classifier_api/classifiers`
- Objects: `https://api-lsst.alerce.online/object_api/list_objects?survey_id=lsst&{params}`
- Features: `https://api-lsst.alerce.online/feature_api/features?survey_id=lsst&oid={oid}`
- Light curve: `https://api-lsst.alerce.online/lightcurve_api/lightcurve?survey_id=lsst&oid={oid}`

### Data flow

1. `fetchClassifiers()` → populates `#sel-classifier` and `classifierClasses` map
2. `onClassifierChange()` → populates `#sel-class`
3. `runQuery()` → fetches object list for each selected class, merges, optionally shuffles and samples N; calls `fetchAllFeatures()`
4. `fetchAllFeatures(oids)` → fetches features for all OIDs in parallel batches of 10; `pivotFeatures()` flattens `[{name, value, fid}]` into `{name_band: value}` dicts; result stored in `featuresData[oid]`
5. `buildFeatureListUI()` → renders checkboxes from `allFeatureNames`
6. `buildPairPlot()` → calls `Plotly.newPlot` with a single `splom` trace; all class colors in `marker.color` array; `selectedpoints` highlights the clicked point across all subplots
7. `onPointSelected(idx)` → calls `Plotly.restyle` to set `selectedpoints`, then `loadObjectDetail()`
8. `loadObjectDetail(obj)` → fetches LC, normalizes detections via `normalizeDet()`, renders with Plotly; also calls `updateAladin()`
9. `updateAladin(ra, dec, oid)` → lazy-initializes Aladin Lite; reuses instance across selections via `aladinInstance.gotoRaDec()`

### State variables

| Variable | Type | Purpose |
|---|---|---|
| `currentSurvey` | string | `'lsst'` or `'ztf'` |
| `objectsData` | array | Object metadata from list endpoint |
| `featuresData` | `{oid: {name: value}}` | Pivoted feature values |
| `selectedClasses` | string[] | Currently added classes |
| `classColorMap` | `{class: hex}` | Color per class for plot |
| `allFeatureNames` | string[] | Union of all feature keys |
| `aladinInstance` / `aladinCat` | Aladin objects | Reused across selections |
| `selectedIdx` | number | Index into `objectsData` |

### Feature normalization (`pivotFeatures`)

ZTF band suffixes: fid 0 → `""`, 1 → `"_g"`, 2 → `"_r"`, 3 → `"_i"`  
Handles three response formats: bare array `[{name, value, fid}]`, wrapped `{features: [...]}`, and dict `{name: value}`.

### Detection normalization (`normalizeDet`)

Unifies field names across ZTF and LSST:
- `mjd`: `mjd` → `midpointMjdTai` → `midPointTai`
- `mag`: `mag` → `psf_mag` → `mag_corr` → `magpsf`
- `band_name`: `band` field (LSST) or `fidMap[fid]` (ZTF)

### Pair plot interaction

- `plotly_click` → `onPointSelected(idx)` → `Plotly.restyle({selectedpoints: [[idx]]})` highlights one point across all subplots
- `plotly_selected` (box/lasso) → shows LC for first selected point; Plotly handles visual selection natively
- `plotly_doubleclick` → resets `selectedpoints: null` (un-highlights all)

### Aladin Lite v3

Loaded asynchronously from `aladin.cds.unistra.fr`. `updateAladin()` polls for `A.init` up to 8 seconds before giving up gracefully. The instance is created once and reused; `aladinCat.removeAll()` clears the previous marker before adding the new one.

## External dependencies (CDN, no install)

- Plotly.js 2.27 — pair plot and light curve
- Font Awesome 6.5 — icons
- Aladin Lite v3 — sky view (async load)

## Reference

See `../ALeRCE_explorer/alerce_explorer.html` for more advanced ALeRCE API usage patterns (ZTF/LSST field-name quirks, forced photometry, E(B-V) fetching, HiPS survey probing, spec-z overlays).
