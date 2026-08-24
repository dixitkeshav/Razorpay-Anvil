# Episode Spec — committed before the generator

This document is authored and committed **before** `src/generator/` is
written, and `src/generator/` is authored **before** any detector exists.
The git history is the evidence that the data was not shaped to fit the
detector. Once `src/generator/` is committed, it is frozen — see
`CLAUDE.md` rule #4. If a phase gate cannot be met, the fix is in the
detector, never here.

---

## 1. Base traffic model

- Volume follows a diurnal curve: low overnight (00:00–06:00 IST), ramping
  through the morning, peak 11:00–14:00 and 19:00–22:00 IST, tapering after.
- Method mix (rough): UPI 55%, cards 25%, netbanking 12%, wallet 6%, EMI 2%.
- Baseline success rate by method sits in the 88–96% band, varying by
  psp/issuer combination — some slices run hotter or colder than the
  overall baseline by design, so a detector must compare each slice against
  its own history, not a global constant.
- Baseline P95 latency by method sits in the 400ms–2.5s band depending on
  method (UPI fastest, netbanking slowest).
- Poisson arrivals per bucket, binomial success draws per bucket at the
  slice's current success-rate parameter.

## 2. Slice lattice

Dimensions: `method × psp × issuer × region × merchant_category`, tested
hierarchically (never the full cross-product):

```
L0  overall
 └ L1  method
    └ L2  method × psp
       └ L3  method × psp × issuer
          └ L4  + region  /  + merchant_id
```

## 3. Difficulty tiers

| Tier | Definition |
|---|---|
| Easy | SR drop > 20pp, high-volume slice |
| Medium | SR drop 8–20pp, medium volume |
| Hard | SR drop 3–8pp, low-volume slice, or confounded by a concurrent volume spike |

Every injected episode is labeled with its tier at generation time, in the
ground-truth field only (`x_episode_id` + a sidecar ground-truth table —
never a field the detector reads).

## 4. Episode types

| ID | Episode | Shape | What it tests | Tier target |
|---|---|---|---|---|
| A | Bank degradation | HDFC × UPI, SR 94→68% over 40 min | basic detection | Easy |
| B | PSP timeout | PSP-A, all banks, P95 800ms→4.8s, SR barely moves | latency leading indicator | Medium |
| C | Card BIN issue | BIN 523xxx, SR 92→41% | deep-lattice attribution | Medium |
| D | Regional | Rajasthan × UPI × PSP-B, SR 93→72% | low-volume slice sensitivity | Hard |
| E | Merchant-specific | M492 × cards, SR 91→54% | merchant-dimension drill-down | Medium |
| F | Calibration drift | SR stable but oracle confidence 0.91 vs realised 0.62 | L10 only — invisible to every other detector | N/A (L10) |
| G | Two concurrent causes | A and C overlapping | attribution honesty; expect failures | Hard |

Each episode has a defined onset, ramp, plateau, and recovery shape (not an
instantaneous step) so that time-to-detect is a meaningful, non-trivial
metric.

## 5. Decoys — must NOT fire the detector

- Volume spikes (flash-sale-shaped traffic bursts) with success rate held
  constant.
- Diurnal troughs (the natural overnight dip) — must not be mistaken for
  degradation.
- Merchant onboarding ramps — a new merchant_id appearing with initially
  noisy, low-volume success rate that is not a real incident.

False alarms on decoys are reported as their own metric in `docs/RESULTS.md`
— this number is at least as informative as recall.

## 6. Ground truth surface

Every injected episode (real or decoy) gets:
- `x_episode_id` on affected `PaymentAttempt` rows (null for unaffected rows).
- A separate ground-truth sidecar table (episode id, type, tier, slice,
  onset, plateau, recovery, decoy flag) used only by `src/evaluation/`.

No module under `src/detection/`, `src/attribution/`, or `src/policy/` may
read either. Enforced by `tests/test_detector_ignores_ground_truth.py`.

## 7. Held-out set (Phase 13)

A second generation run, fresh seeds, redrawn parameters within the same
distributions described above — not the same episodes replayed. Headline
metrics in `docs/RESULTS.md` come from the held-out set only. Generated
exactly once, via `make holdout`.
