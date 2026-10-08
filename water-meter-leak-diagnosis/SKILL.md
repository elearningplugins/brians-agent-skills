---
name: water-meter-leak-diagnosis
description: >-
  Reads a residential water meter from a phone video or photo, reconciles it
  against the utility bill, and isolates where water is going (irrigation,
  house supply line, fixtures) with shutoff tests. Use when the user shares a
  water meter video, asks what the numbers on their meter mean, has a high
  water bill, suspects a leak, or is choosing a leak monitor such as Flume.
---

# Water meter leak diagnosis

The meter is the instrument. Every conclusion must come from readings taken off the meter face or the bill, with timestamps, not from how plausible a cause sounds.

## Workflow

```
- [ ] 1. Extract frames and read the meter
- [ ] 2. Identify meter make, model, size and units
- [ ] 3. Build a readings log with times
- [ ] 4. Reconcile against the bill
- [ ] 5. Isolate the flow with shutoff tests
- [ ] 6. Recommend fixes and monitoring
- [ ] 7. Offer a notes file for future troubleshooting
```

### 1. Extract frames and read the meter

Phone videos of meter pits are often upside down. Run the bundled script and read whichever sheet is legible:

```bash
bash scripts/meter_frames.sh <video> <out_dir> [fps] [crop]
```

It writes `upright/` and `rotated/` frames plus numbered `sheet_upright_NN.jpg` and `sheet_rotated_NN.jpg` contact sheets covering the whole clip, and prints duration and `creation_time`. Once the display location is known, rerun with a crop (`w:h:x:y`) to zoom on the LCD. Then view individual frames to confirm digits; contact sheets are too small for decimals.

Record every screen the display cycles through, not only the big number. Digital registers alternate between total, a short total, a model screen, and flow rate.

### 2. Identify meter make, model, size and units

- Read brand text and date codes on the lid.
- On a Badger HR-E LCD, the model screen (for example `d 70 9`) gives meter type, model, and resolution. See [references/badger-hr-e-lcd.md](references/badger-hr-e-lcd.md).
- Infer units from the decimal count at the meter size's resolution; never assume gallons because the utility bills in gallons.
- For other brands, search the register's user manual before interpreting any screen. Do not guess what an unlabeled screen means.

### 3. Build a readings log

| Time | Reading | Flow screen | Conditions |
|---|---|---|---|

Use the video `creation_time` (UTC; convert to local) for each clip and the in-video seconds for changes within a clip. Note what was on or off: irrigation, main valve, known fixtures.

A short clip cannot rule out a slow drip: at 0.01-gallon resolution, one drop per second moves the last digit about every 13 minutes. Say so instead of declaring "no leak" from 90 seconds.

### 4. Reconcile against the bill

- Bills usually show readings truncated to billing units (for example thousands of gallons). Treat a bill read of `253` as a range, 253,000–253,999.
- Check that the current meter read is consistent with the last bill read and the bill's daily rate. A large mismatch suggests a misread, an estimated read, or the wrong meter.
- Compare usage with the winter average (indoor baseline). The excess over it is the outdoor or leak share.
- Note the meter ID on the bill and ask the user to confirm it against the meter body or lid sticker.
- Show tier math when usage pushed the bill into higher-priced tiers.

### 5. Isolate the flow

Run these in order, reading the meter before and after each with all known use stopped:

1. Everything off for 15–30 minutes (overnight is best). Movement means a leak.
2. Irrigation backflow valve or irrigation isolation valve off. If the meter stops, the leak is in the irrigation system.
3. House main shutoff closed. If the meter still moves, the leak is in the service line between meter and house (usually the owner's responsibility). If it stops, the leak is inside.
4. Inside: food-coloring test in each toilet tank; check faucets, water heater relief line, softener, ice maker.

For irrigation, distinguish a scheduled run (several gpm per zone, on a schedule) from a valve weeping through or a broken line (sub-gpm, continuous, often with soggy ground or a draining low head). Test by restoring irrigation supply with the controller off.

Midday sub-gpm flow that stops when irrigation is isolated points to a weeping zone valve or underground leak, not normal watering.

### 6. Recommend fixes and monitoring

- Convert flow to cost terms: gpm × 1,440 = gallons per day.
- Suggest calling the utility about a leak adjustment once the leak is fixed; keep repair receipts.
- For monitors, choose by where the leak can be relative to the device. See [references/leak-monitors.md](references/leak-monitors.md). Verify compatibility, current prices, and any utility rebate with fresh searches.

### 7. Offer a notes file

Offer to write the findings as Markdown: meter identity and screen meanings, readings log, bill reconciliation, test procedure, open to-dos, and monitor research. If publishing it (for example a secret gist), leave out account numbers and street addresses and tell the user what was omitted.

## Honesty rules

- Quote digits only after reading them from a zoomed frame; mark uncertain digits as uncertain.
- Never state the unit, meter size, or a screen's meaning without a source: the display itself, the manufacturer manual, or the utility.
- Do not present coupon-site promo codes as valid, or third-party claims of utility rebates as confirmed, without an official source.
- If the user did not say whether water was in use during a clip, ask before calling movement a leak.
