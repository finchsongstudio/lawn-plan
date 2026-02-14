# KC Lawn Care 2026 — Spreadsheet Improvement Instructions

## Summary

The current spreadsheet faithfully implements the KC plan's Andersons granular backbone + GCI liquid biostimulant/fungicide hybrid. The main gap is **post-emergent weed control** — there's only one entry (Surge 16-0-9 in April). The GCI Cool Season Liquid Guide builds spot-spray herbicide options into nearly every round. The instructions below add those missing entries and make a few other refinements.

---

## 1. Add Post-Emergent Weed Control Rows

Add the following rows to the spreadsheet. Each is an **"if needed"** conditional application — you only spray if weeds are visible. These slot alongside existing applications in the same time window.

### 1A — Early Spring Broadleaf Spot-Spray (March)

| Field | Value |
|---|---|
| **Application** | Early Spring Post-Emergent (if needed) |
| **Month** | March |
| **Projected Date** | Same as `round1_preemergent` |
| **Reason** | Same as round1_preemergent — spot-spray visible broadleaf weeds at time of pre-emergent |
| **Products** | `Other — SpeedZone Herbicide (liquid) - 1.0 oz/1k` + `GCI — Natural Adjuvant (liquid) - 0.5 oz/1k` |
| **Conditions** | Air temp ≥ 50°F. Do NOT water for 12-24h after. SpeedZone works at cooler temps than Triad — preferred for early spring. |
| **Warnings** | If using Triclopyr instead of SpeedZone: 0.75 oz/1k, max 70°F, use 1 gal water/1k minimum. Never apply Triclopyr above 70°F. |
| **app_id** | `spring_postemergent_early` |

**Why:** The GCI guide includes SpeedZone or Triclopyr as an optional add-on to Round 1. Early spring is when cool-season broadleaf weeds (dandelion, henbit, chickweed) are young and most vulnerable. The current schedule has no weed control until April.

---

### 1B — Keep Existing Surge in April (No Change Needed)

The existing `round2_postemergent` entry (Andersons Surge 16-0-9, April) stays as-is. This is the primary broadleaf pass and aligns with both the Andersons calendar and GCI's Round 2 timing. The 60–85°F window is correct.

**Optional enhancement:** Add a note to the Conditions or Warnings column:

> Alternative: Triad Select 3-Way (liquid) at 1 oz/1k + Natural Adjuvant 0.5 oz/1k for targeted spot-spray instead of granular blanket app. Max 85°F. May have mixing issues with adjuvant at 1 qt/1k calibration — use 2 qt or 1 gal/1k.

---

### 1C — Late Spring Broadleaf Spot-Spray (May)

| Field | Value |
|---|---|
| **Application** | Late Spring Post-Emergent (if needed) |
| **Month** | May |
| **Projected Date** | Same window as `bio3_calcium` |
| **Reason** | Catch broadleaf weeds that broke through pre-emergent. Combine with Cal-Tide window. |
| **Products** | `Other — SpeedZone Herbicide (liquid) - 1.0 oz/1k` + `GCI — Natural Adjuvant (liquid) - 0.5 oz/1k` |
| **Conditions** | Air temp 60–85°F. Do NOT water for 12-24h after. Can tank-mix with Cal-Tide IF you accept the 12-24h no-water restriction (Cal-Tide normally waters in immediately). Easier to do as a separate spot-spray pass. |
| **Warnings** | For persistent broadleaf (wild violet, creeping charlie): use Triclopyr 0.75 oz/1k + Adjuvant 0.5 oz/1k instead. Triclopyr max 70°F — only viable in early May in KC. |
| **app_id** | `spring_postemergent_late` |

---

### 1D — Nutsedge Treatment (June–July, Conditional)

| Field | Value |
|---|---|
| **Application** | Nutsedge Control (if needed) |
| **Month** | June–July |
| **Projected Date** | When nutsedge is actively growing |
| **Reason** | Nutsedge is common in KC. Pre-emergent does not control it. Must be treated post-emergent when actively growing. |
| **Products** | `Other — Halo Select WDG (liquid) - per label rate/1k` + `GCI — Natural Adjuvant (liquid) - 0.5 oz/1k` |
| **Conditions** | Air temp 60–90°F. Nutsedge must be actively growing. Do NOT water for 24h after. May need 2 applications 2-3 weeks apart for full control. |
| **Warnings** | Do not confuse nutsedge with crabgrass — nutsedge has a triangular stem cross-section and lighter green color. Halo does not control broadleaf or grassy weeds. |
| **app_id** | `nutsedge_control` |

---

### 1E — Late Summer Weed Cleanup (August)

| Field | Value |
|---|---|
| **Application** | Late Summer Weed Cleanup (if needed) |
| **Month** | August |
| **Projected Date** | Same window as `august_iron`, at least 28 days before fall overseed |
| **Reason** | Final weed control window before fall renovation. GCI Round 4 includes spot-spray options. |
| **Products** | `Other — SpeedZone Herbicide (liquid) - 1.0 oz/1k` + `GCI — Natural Adjuvant (liquid) - 0.5 oz/1k` |
| **Conditions** | MUST be applied ≥ 28 days before fall overseeding date. Air temp 60–85°F. Do NOT water for 12-24h after. |
| **Warnings** | Hard 28-day cutoff before overseeding is non-negotiable — herbicide residue kills new seedlings. If your overseed target is Sep 10, last herbicide date is Aug 13. |
| **app_id** | `summer_postemergent_late` |

---

### 1F — Crabgrass Cleanup Before Fall Seeding (August–September)

| Field | Value |
|---|---|
| **Application** | Crabgrass Cleanup (if needed) |
| **Month** | August–September |
| **Projected Date** | 1–4 weeks before fall overseed |
| **Reason** | Quinclorac can be applied up to 1 week before seeding — much tighter window than other herbicides. Cleans up crabgrass breakthrough before renovation. |
| **Products** | `Other — Quinclorac 1.5L (liquid) - 1.5 oz/1k` + `Other — Methylated Seed Oil (MSO) - 0.5 oz/1k` |
| **Conditions** | Safe to apply up to 7 days before overseeding (unlike 28-day cutoff for broadleaf herbicides). Use MSO as surfactant, NOT Natural Adjuvant. Crabgrass must be actively growing. |
| **Warnings** | Quinclorac only controls crabgrass and a few other grassy weeds — does not control broadleaf. Do not use Natural Adjuvant with this product. |
| **app_id** | `crabgrass_cleanup` |

---

## 2. Add GCI Sea-K to Fungicide Tank Mixes

The GCI guide includes **Sea-K at 0.5 oz/1000** in Fungicide App 2 (June) and pairs it with Five 0 Five in several apps. The KC plan's JSON omits Sea-K entirely, but it's a low-effort add for drought/heat stress tolerance — valuable for KC summers.

### Changes to Existing Rows

**`fungicide2` (June)** — Add to Products column:
```
GCI / N-Ext
  Sea-K (liquid) - 0.5 oz/1k, 1.0 oz total
```

**`fungicide4` (August)** — The existing entry already includes Microgreene and Five 0 Five. Add Sea-K:
```
GCI / N-Ext
  Sea-K (liquid) - 0.5 oz/1k, 1.0 oz total
```

---

## 3. Add D-Thatch to a Bio App

The GCI guide includes **N-Ext D-Thatch** for biological thatch reduction. The KC plan omits it, but KC's KBG can build up thatch quickly, especially with the nitrogen budget in this program (3.5–4.5 lbs N/1000/year).

### Recommended Placement

Add D-Thatch to the **`bio4_humic` (June)** row, since that app is currently just Humic12 alone:

**Updated Products for `bio4_humic`:**
```
GCI / N-Ext
  Humic12 (liquid) - 9 oz/1k, 18.0 oz total
  D-Thatch (liquid) - 6 oz/1k, 12.0 oz total
```

**Updated Conditions:** Water in. Do NOT use Natural Adjuvant with Humic12 or D-Thatch.

---

## 4. Clarify "per label" Rates

Several rows use **"per label"** instead of specific rates. This makes the spreadsheet harder to use as a quick reference. Where possible, fill in actual rates:

| app_id | Product | Suggested Specific Rate |
|---|---|---|
| `round1_preemergent` | Andersons Barricade | Look up bag rate for split app (typically ~3.5 lbs/1k for 0.375 AI split). Confirm from your specific bag. |
| `round2_postemergent` | Andersons Surge 16-0-9 | Typically 4–6 lbs/1k depending on weed pressure. Confirm from bag label. |
| `round4_iron` | Lean & Green 2-0-0 + Fe | Typically 4 lbs/1k. Confirm from bag label. |
| `august_iron` | Lean & Green 2-0-0 + Fe | Same as above. |
| `grub_preventive` | GrubOut 17-0-3 | Typically 2.87 lbs/1k. Confirm from bag label. |
| `bio3_calcium` | Hydra Charge | Typically 2.5 lbs/1k. Confirm from bag label. |

---

## 5. Add a "Category" Column

The current spreadsheet has no way to filter by type of application. Add a **Category** column with these values, matching the KC plan JSON:

| Category Value | Applies To |
|---|---|
| `pre_emergent` | round1_preemergent, fall_preemergent |
| `fertilizer` | round1_fertilizer, round2_fertilizer, round3_fertilizer, round4_iron, august_iron, round5_fall_fert, round6_winterizer, round7_backup_winterizer |
| `post_emergent` | round2_postemergent, and all new weed control rows |
| `biostimulant` | bio1 through bio7 |
| `fungicide` | fungicide1 through fungicide4 |
| `insecticide` | grub_preventive |
| `renovation` | fall_renovation |

This lets you filter the sheet to see, for example, just the fertility program or just the weed control schedule at a glance.

---

## 6. Add Total N Tracking Column

The KC plan targets **3.5–4.5 lbs N per 1,000 sq ft per year**. Add a column called **N (lbs/1k)** to track cumulative nitrogen. The JSON already has these values:

| app_id | N lbs/1k |
|---|---|
| round1_fertilizer | 0.48 |
| round2_fertilizer | 0.50 |
| round2_postemergent (Surge 16-0-9) | ~0.64 (16% of ~4 lbs) |
| round3_fertilizer | 0.96 |
| round4_iron (DGL option) | 0.25 |
| round5_fall_fert | 0.50–0.75 |
| fall_renovation (12-8-12) | 0.48 |
| round6_winterizer | 0.48 |
| round7_backup_winterizer | 0.25–0.50 |

Running total (excluding optional/conditional): approximately **3.40–4.05 lbs N/1k**, which lands in the target range. Adding the backup winterizer and DGL summer option pushes you toward the upper end. Tracking this in the spreadsheet prevents accidental over-fertilization.

---

## Summary of All New Rows to Add

| app_id | Application | Month | Key Product |
|---|---|---|---|
| `spring_postemergent_early` | Early Spring Post-Emergent (if needed) | March | SpeedZone 1 oz/1k |
| `spring_postemergent_late` | Late Spring Post-Emergent (if needed) | May | SpeedZone or Triclopyr |
| `nutsedge_control` | Nutsedge Control (if needed) | June–July | Halo Select WDG |
| `summer_postemergent_late` | Late Summer Weed Cleanup (if needed) | August | SpeedZone 1 oz/1k |
| `crabgrass_cleanup` | Crabgrass Cleanup (if needed) | Aug–Sep | Quinclorac 1.5L + MSO |

## Summary of Existing Row Modifications

| app_id | Change |
|---|---|
| `round2_postemergent` | Add note about Triad Select 3-Way as liquid alternative |
| `fungicide2` | Add Sea-K 0.5 oz/1k |
| `fungicide4` | Add Sea-K 0.5 oz/1k |
| `bio4_humic` | Add D-Thatch 6 oz/1k |

## Summary of New Columns to Add

| Column | Purpose |
|---|---|
| **Category** | Filter by application type (pre_emergent, fertilizer, post_emergent, etc.) |
| **N (lbs/1k)** | Track cumulative nitrogen to stay within 3.5–4.5 lbs/year budget |
