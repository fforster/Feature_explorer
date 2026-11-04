# ALeRCE API Reference

**`feature_explorer.html` uses the multisurvey TAP service (first section below) for all data.** The per-survey REST APIs further down are kept for reference only (legacy; the REST ZTF features come from the old `lc_classifier_1.2.1-P` pipeline, not the reprocessed multisurvey data).

---

## Multisurvey TAP (primary)

- Endpoint: `https://tap.alerce.online/tap` (sync: `/tap/sync`), schema `alerce_tap`, GAVO DaCHS over PostgreSQL. Browse: `https://tap.alerce.online/browse/alerce_tap/multisurvey_lowercase`.
- Request: `POST /tap/sync` form fields `REQUEST=doQuery&LANG=ADQL&FORMAT=csv&MAXREC=…&QUERY=…`. Errors come back as a VOTable with `<INFO name="QUERY_STATUS" value="ERROR">message</INFO>`.
- **No CORS headers** (as of 2026-11): browsers can't call it cross-origin; the preflight `OPTIONS` returns 500. A form POST needs no preflight, so only `Access-Control-Allow-Origin` is missing. Use `tap_proxy.py` meanwhile.
- **Use CSV, not JSON**: JSON returns 64-bit oids as numbers (precision loss in JS).
- ADQL dialect: no `RAND()`, no scalar subqueries in `WHERE` (use joins); `MOD(oid, k)` works for hash sampling; `ORDER BY probability DESC` is index-backed and fast. ~1.7 s fixed cost per query; little gain beyond ~2 concurrent queries.

### Identity

| Key | Meaning |
|---|---|
| `sid` | survey: 0 = ZTF, 1 = LSST DIA object, 2 = LSST solar-system object |
| `tid` | telescope: 0 = ZTF, 1 = Rubin (used by `classifier`, `feature_name_lut`) |
| `oid` | int64. ZTF: `(1<<55) + year·26⁷ + base-26 letters` of `ZTFyyabcdefg`. LSST: `diaObjectId` |

Always join per-object tables on `(oid, sid)`. ZTF extension tables (`ztf_detection`, `ztf_forced_photometry`) have no `sid` column: join on `oid + measurement_id`.

### Tables used by the explorer

| Purpose | Table(s) | Key columns |
|---|---|---|
| Classifiers | `classifier` | `classifier_id, classifier_name, classifier_version, tid` |
| Classes | `taxonomy` | `classifier_id, class_id, class_name, taxonomy_order` |
| Classifications | `probability` | `oid, sid, classifier_id, class_id, classifier_version, probability, ranking` (`ranking = 1` = top class) |
| Object summary | `object` | `oid, sid, meanra, meandec, n_det, n_forced, firstmjd, lastmjd` |
| Features | `feature` + `feature_name_lut` + `feature_version_lut` | `oid, sid, feature_id, band, version, feature_value`; only the latest value per object × feature |
| Bands | `band` | ZTF 1 g, 2 r, 3 i; LSST 1 g, 2 r, 3 i, 4 z, 5 y, **6 u**. `feature.band`: 0 = none, multi-digit = band set (12 = g+r) |
| ZTF LC | `detection ⋈ ztf_detection`, `forced_photometry ⋈ ztf_forced_photometry`, `ztf_non_detection` | `magpsf, sigmapsf, magpsf_corr, sigmapsf_corr, isdiffpos (±1)`; fp: `mag, e_mag, mag_corr, e_mag_corr, isdiffpos`; limits: `diffmaglim` |
| LSST LC | `detection ⋈ lsst_detection`, `forced_photometry ⋈ lsst_forced_photometry` | `psfflux, psffluxerr, scienceflux, sciencefluxerr` in **nJy** |

### Model time references (stored as features)

`SPM_mjd_ref` (first observation), `fleet_mjd_ref_{band}` (first point with flux > 1 µJy incl. forced phot), `TDE_mjd_ref_{band}` (brightest point incl. forced phot), `ulens_mjd_ref` (first point with e_mag < 1). Missing for some older LSST feature versions.

---

# Legacy REST APIs

ALeRCE operates two independent API stacks — one for ZTF, one for LSST. They share similar resource names but differ in base URLs, parameter names, and response field names.

---

## Base URLs

| Survey | Base |
|---|---|
| ZTF | `https://api.alerce.online/ztf/v1` |
| LSST | `https://api-lsst.alerce.online` (each resource has its own sub-path) |

---

## Classifiers

| Survey | Endpoint |
|---|---|
| ZTF | `GET https://api.alerce.online/ztf/v1/classifiers` |
| LSST | `GET https://api-lsst.alerce.online/classifier_api/classifiers` |

Response: array of classifier objects. Each has a `name` and a `classes` array of class name strings.

---

## Object list

| Survey | Endpoint |
|---|---|
| ZTF | `GET https://api.alerce.online/ztf/v1/objects?{params}` |
| LSST | `GET https://api-lsst.alerce.online/object_api/list_objects?survey_id=lsst&{params}` |

### Common query parameters

| Parameter | ZTF name | LSST name | Notes |
|---|---|---|---|
| Classifier | `classifier` | `classifier` | |
| Class | `class` | `class_name` | ZTF uses `class`, not `class_name` |
| Min probability | `probability` | `probability` | |
| Min detections | `ndet` | `n_det` | Different name! |
| Page | `page` | `page` | 1-indexed |
| Page size | `page_size` | `page_size` | Max 100 |
| Ranking | `ranking=1` | *(not needed)* | ZTF requires this to get the top classifier result |
| Count | `count=false` | `count=false` | Skip total-count query for speed |

### Response

Both return `{ items: [...] }` (or a bare array for some ZTF endpoints).

**ZTF field names differ from LSST** — normalize after fetching:

| Canonical name | ZTF field | LSST field |
|---|---|---|
| `class_name` | `class` | `class_name` |
| `meanra` | `ra` | `meanra` |
| `meandec` | `dec` | `meandec` |
| `n_det` | `ndet` | `n_det` |

---

## Features

| Survey | Endpoint |
|---|---|
| ZTF | `GET https://api.alerce.online/ztf/v1/objects/{oid}/features` |
| LSST | `GET https://api-lsst.alerce.online/feature_api/features?survey_id=lsst&oid={oid}` |

### ZTF response format

Returns a bare array `[{name, value, fid}, …]`.

`fid` band mapping: `0` → global (no suffix), `1` → `_g`, `2` → `_r`, `3` → `_i`.

Pivot to `{name_band: value}` dict — e.g., `SPM_A` with `fid=1` → key `SPM_A_g`.

Also handles wrapped `{features: [...]}` and plain dict `{name: value}` response shapes for robustness.

### LSST response format

Returns a dict `{name: value}` or wrapped object — no `fid` field; band is already embedded in the feature name.

---

## Light curve

| Survey | Endpoint | Notes |
|---|---|---|
| ZTF v1 | `GET https://api.alerce.online/ztf/v1/objects/{oid}/lightcurve` | Detections only; may include `mag_corr` on some objects |
| ZTF v2 | `GET https://api.alerce.online/v2/lightcurve/lightcurve/{oid}?survey_id=ztf` | Adds `mag_corr`/`e_mag_corr` and `forced_photometry` |
| LSST | `GET https://api-lsst.alerce.online/lightcurve_api/lightcurve?survey_id=lsst&oid={oid}` | Single endpoint |

### Detection field names

| Canonical | ZTF field | LSST field |
|---|---|---|
| `mjd` | `mjd` | `midpointMjdTai` or `midPointTai` |
| `mag` (diff-image) | `magpsf` | `psf_mag` |
| `e_mag` | `sigmapsf` | `sigma_mag` |
| `band_name` | derived from `fid` via fidMap | `band` |
| `psfFlux` (µJy, diff) | derived or `psfFlux` | `psfFlux` |
| `psfFluxErr` | derived or `psfFluxSigma` | `psfFluxSigma` or `psfFlux_err` |

`mag_corr` / `e_mag_corr` — ZTF science (corrected) magnitude. `e_mag_corr = 100.0` is a sentinel for unreliable corrections; discard any detection where `e_mag_corr >= 1.0`.

### ZTF v2 response keys

- `detections` — same detections as v1 but enriched with `mag_corr`/`e_mag_corr`; cross-match to v1 by `candid`
- `forced_photometry` — pre-alert forced-phot records; fields: `mjd`, `mag`, `e_mag`, `fid`, `isdiffpos`

`isdiffpos` encoding: `1`, `'1'`, `true`, or `'t'` → positive flux; anything else → negative. Flux (µJy) = `sign × 10^((23.9 − mag) / 2.5)`.

---

## Flux / magnitude conversions

AB zero-point: `ABZP = 23.9` (microjansky scale).

```
flux_µJy = 10^((23.9 − mag) / 2.5)
mag      = 23.9 − 2.5 × log10(flux_µJy)
flux_err = flux × e_mag × ln(10) / 2.5
```

---

## Key gotchas

- **ZTF requires `ranking=1`** on object queries or you get duplicate rows (one per classifier ranking).
- **ZTF uses `ndet`; LSST uses `n_det`** — passing the wrong name silently returns unfiltered results.
- **ZTF uses `class`; LSST uses `class_name`** in both query params and response objects.
- **`mag_corr` is never the difference-image mag** — it is the science/corrected mag. The difference-image mag is always `magpsf`/`psf_mag`.
- **v1 may already have `mag_corr`** on some ZTF objects; check before fetching v2.
- **Forced-photometry extends the timeline** before the first alert detection. For model overlays that need the earliest observation in a band (e.g. FLEET), use forced-phot MJDs, not just alert MJDs.
