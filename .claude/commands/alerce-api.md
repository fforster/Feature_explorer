# ALeRCE API Reference

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
