---
name: youth-soccer-player-analysis
description: >-
  Builds a local, privacy-preserving analysis of one youth soccer player from a
  recorded game: detection, tracking, team split by kit, jersey-number
  identification, field calibration, and a per-player report with clips. Use
  when the user wants heatmaps, spacing, distance, minutes played, or
  highlight clips for a specific player from Trace, Veo, phone, or drone game
  video, or asks which open-source soccer tracking tools fit amateur footage.
---

# Youth soccer player analysis

The goal is a report about one player that a parent or coach can trust. Every number must come from a confirmed track of that player on a calibrated field. When identity or calibration is uncertain, mark the stretch unconfirmed and leave it out of the stats instead of guessing.

## Workflow

```
- [ ] 1. Check the machine before installing anything
- [ ] 2. Identify how the game was filmed
- [ ] 3. Prove each stage on a 2-minute stretch before running the whole game
- [ ] 4. Detect and track players
- [ ] 5. Split teams by kit colour
- [ ] 6. Calibrate the camera to the field
- [ ] 7. Identify the target player by jersey number
- [ ] 8. Compute metrics and build the report
```

### 1. Check the machine

Run `sysctl -n machdep.cpu.brand_string`, `df -h`, and `python3 --version` first.

- Intel Macs cannot use PyTorch `mps`, and PyTorch stopped shipping Intel-Mac wheels after 2.2. Use the pins in [references/environment.md](references/environment.md).
- A game video plus models and intermediates needs roughly 15–20 GB free. A full disk fails mid-install with `No space left on device`.
- Time the detector on real frames before promising a schedule. On a 2019 quad-core i5, the Roboflow player model took 3.4 s/frame at `imgsz=1280`, 1.9 s at 960, and 1.0 s at 640 (640 missed distant players). A 54-minute game at 2 fps and 960 is about 3 hours.

### 2. Identify how the game was filmed

Ask the user which camera recorded it, then confirm from the video. Do not infer the camera type from how the footage looks: an elevated, panning view can be a drone or a fixed-pole camera with a virtual pan.

```bash
python scripts/camera_check.py <video> --pairs 1800:1805 1800:1830 3060:3070
```

Low median background error (under about 1 px) on pairs seconds apart means one homography explains the whole view: the camera centre is fixed and only rotates or zooms. Trace and Veo exports behave this way. Large background error with good matches means the camera itself moves (drone, handheld).

| Camera | Calibration approach |
|---|---|
| Fixed-position virtual camera (Trace, Veo follow view) | Register frames on background features, then fit one camera pose and field size for the whole game |
| Fixed tripod, no pan | Calibrate once |
| Panoramic export (Veo, Trace panorama if available) | Calibrate once; the target player is always in frame, so distance is fully measured |
| Moving camera (drone, handheld) | Per-frame calibration; expect much lower reliability |

With a follow-the-ball view, players far from the ball leave the frame. Report distance as **measured** (on screen, confirmed) and **estimated** (measured pace × minutes played) and label which is which.

### 3. Prove each stage on a short stretch

Pick a 2-minute stretch where field lines are visible. Validate each stage with an image or table before running the full game overnight. Contact sheets (`ffmpeg ... -vf "fps=1/180,scale=320:-1,tile=3x6"`) show camera behaviour and kit changes across the whole file quickly.

### 4. Detect and track

Use the Roboflow `sports` soccer player detector (classes: ball, goalkeeper, player, referee) through Ultralytics, with BoT-SORT (`tracker="botsort.yaml"`, `gmc_method: sparseOptFlow`) rather than ByteTrack, because BoT-SORT compensates for camera motion.

Known weaknesses on amateur footage, measured on a U11 Trace clip at 5 fps:

- The ball was found in 7% of frames. Possession needs a dedicated ball model or interpolation, not the player model's ball class.
- Tracks broke constantly: median length 8 frames, 257 tracks in 75 seconds. Plan to link fragments by field position after calibration, not by image position.
- The detector's `referee` class is unreliable: 56 of 66 "referee" tracks were players in a dark kit. Reclassify by kit colour.

### 5. Split teams by kit colour

Take the torso (rows 15–50% of the box, middle 60% of columns), drop grass pixels by HSV, and use the median Lab colour. Cluster with KMeans (k≈6) with chroma weighted over lightness (`L×0.5, a×2, b×2`).

- A white kit splits into shade and sun clusters. Assign **neutral** clusters (chroma < ~12) to teams by lightness, and treat strongly coloured clusters (yellow referees, green or pink keepers) as `other`.
- Vote per track; label a track unknown below about 60% agreement.
- Always render a crop sheet per label and look at it before trusting the split.

### 6. Calibrate the camera to the field

Off-the-shelf calibration models trained on pro broadcast (PnLCalib/NBJW, Roboflow pitch keypoints) failed on amateur footage: zero lines detected, keypoints in empty grass, about 9 s/frame on CPU. Pro keypoints also map to the wrong spot on a small-sided field because marking proportions differ. Use the field template in [references/field-and-calibration.md](references/field-and-calibration.md).

For a fixed-position virtual camera:

1. Register sampled frames by chaining SIFT + RANSAC homographies on background features. Check drift by comparing chained and direct homographies between frames 10–60 s apart.
2. Detect line pixels (white top-hat on grass), then straight segments with `HoughLinesP`. Keep long segments and drop the spectator band just inside the far grass edge; short flat segments on open grass are mowing stripes.
3. Fit one camera pose plus field length and width to segments from many frames, with bounded parameters and the camera prior (pole at the halfway line, off the near touchline).
4. Render the template over several frames and inspect the overlay. Do not compute metrics until the overlay lines up.

Status: steps 1–2 are validated; step 3 is not yet validated. See the reference file for what failed and why.

### 7. Identify the target player

- Ask for the player's number and kit colours; read the number colour from crops instead of assuming it.
- Crop the torso (rows 10–60% of the box), upscale ×4, run EasyOCR with `allowlist="0123456789"`, keep 1–2 digit reads.
- Vote per track, weighting by confidence. Thin `1`s are often dropped (`15` reads as `5`), so when a track has both a two-digit read and its trailing digit, prefer the two-digit number.
- Carry identity along a track between reads. Mark stretches without a confident vote as unconfirmed and exclude them from stats.
- Never ask the user to click through the game unless they request a manual mode.

### 8. Metrics and report

Compute on confirmed, calibrated stretches only: heatmap and average position by half and by phase (team in or out of possession), spacing to nearest teammate, drift from the assigned role, distance, sprints, top speed (smoothed over 1-second windows), recovery time to goal-side after a turnover, minutes played per stint, and 5–10 clips centred on the player.

Also report how much game time the video covers. Small-sided halves are fixed length, so a shorter video means missing game time; do not count minutes that were not recorded.

## Honesty and privacy rules

- Process video only on the local machine; do not upload to hosted inference or labelling services.
- Share only clips centred on the target player, and follow club and league video policy.
- Do not publish the player's name, number, team, or opponent in reusable artifacts.
- State per metric whether it is measured, estimated, or not available, and why.
- Before calling any number trustworthy, compare about 20 flagged moments against the video by eye.

## Additional resources

- [references/environment.md](references/environment.md): install pins and timings for Intel Macs
- [references/field-and-calibration.md](references/field-and-calibration.md): 9v9 template, calibration attempts and results
- [references/prior-art.md](references/prior-art.md): open-source projects surveyed, what to reuse, licences
