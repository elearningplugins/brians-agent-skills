# Badger Meter HR-E LCD register

Common on US residential disc meters (Recordall Models 25/35/40/55/70). Identify it by "HR-E LCD" printed on the lid, a 9-digit LCD, and a four-digit date code such as `12/23`.

Source: Badger Meter *HR-E LCD, HR-E LCD 4-20 Encoder User Manual* (badgermeter.com). Re-check it for other registers.

## Screen cycle

The display toggles on its own; no button press is needed.

| Screen | Example | Meaning | Duration |
|---|---|---|---|
| 9-digit total | `0260233.15` | Lifetime volume, forward flow minus reverse flow | ~45 s |
| 6-digit total | `0260 23` | Same total mimicking a 6-wheel odometer; moving segments ("flow finder") appear when water flows | ~5 s |
| Meter model | `d 70 9` | Meter type, model, digit resolution | ~5 s |
| Rate of flow | `0.20` | Average flow over the prior minute, default gallons per minute; leading `-` means reverse flow | ~5 s |

A new encoder ships in storage mode and shows only the meter-model screen until the meter turns twice.

## Meter-model screen

- First character is the meter type: `d` disc, stylized `T` turbo, `C` compound.
- Middle number is the Badger Recordall model, which sets the size: LP and 25 = 5/8", 35 = 3/4", 40/55/70 = 1", 120 = 1.5", 170 = 2". Turbo models: T160 = 1.5", T200 = 2", T450 = 3", T1000 = 4".
- Last number is the digit resolution the encoder reports (9 = full resolution).
- Unit label (GAL, FT3, M3) may also appear, but is often too small or glared to read on video.

## Inferring units from decimals

At full 9-digit resolution the decimal places identify the unit:

| Meter size | Gallons | Cubic feet | Cubic meters |
|---|---|---|---|
| 5/8"–1" | 0.01 (2 decimals) | 0.001 (3 decimals) | 0.0001 (4 decimals) |
| 1.5"–4" | 0.1 | 0.01 | 0.001 |

So a 1" Model 70 showing `0260233.15` reads 260,233.15 gallons.

## Billing digits

Short indicator lines above/below the leading digits mark the utility's billing units (the white wheels on a mechanical register). For a utility billing per 1,000 gallons, the billing read is the digits left of the hundreds place: `0260233.15` bills as `260`.

## Status indicators

Shown in the bottom-left corner. They light while active and dim when cleared.

| Indicator | Trigger | Clears |
|---|---|---|
| Check mark | Encoder operating correctly | n/a |
| Encoder alarm | Removal, temperature outside 34–140 °F, or magnetic tamper | After 35 days without recurrence |
| Reverse flow | Reverse flow detected | After 35 days without recurrence |
| Suspected leak | 24 hours without one 15-minute no-flow interval | When a 15-minute no-flow interval occurs |
| 30-day no usage | No flow for 30 days | When flow resumes |
| End of battery life | ~19 years of calculated use | Never |

The suspected-leak icon is a free continuous-leak check: if it is lit, water has not stopped for a full day.
