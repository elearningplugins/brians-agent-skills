# Leak monitor options

Prices, rebates, and promo codes change constantly. Re-verify every number here with a fresh search before quoting it, and never present a coupon-site code as working unless it was confirmed.

## Choosing by where the leak can be

The deciding question is where the device sits relative to the irrigation tap. In many US cities the sprinkler line tees off between the meter and the house, so anything installed on the house main never sees it.

| Device type | Examples | Sees irrigation? | Shuts water off? |
|---|---|---|---|
| Meter-mounted sensor | Flume 2, Flume 2X | Yes, everything through the meter | No, alerts only |
| Inline on house main | Phyn Plus, Moen Flo | Only if irrigation tees off downstream | Yes |
| Irrigation flow sensor | Rachio flow meter, Hunter Hydrawise | Irrigation only | Controller can stop zones |
| Spot sensors | YoLink, Govee, Moen pucks | No; only water at the puck | Some kits pair with a valve |

## Flume

- Straps onto the meter and reads the meter's drive magnet; no plumbing. A Wi-Fi bridge goes indoors.
- Compatibility: check Flume's list and offer the user a photo upload. Badger Recordall/LP models 25–200 and HR-E/HR-E LCD encoders are listed compatible up to 2"; the square Badger E-Series, Neptune Mach 10, Sensus iPERL and Sensus OMNI are not.
- Flume 2X versus Flume 2: same sensing and app. 2X adds a parylene coating, upgraded Wi-Fi, and two standard AA battery packs. Prefer 2X for wet or deep meter pits.
- Detection floor depends on meter size: about 0.01–0.03 gpm on 5/8"–3/4" meters and 0.02–0.07 gpm on 1"–1.5" meters. Slower drips accumulate and show as occasional blips rather than continuous flow.
- Default alerts: Smart Leak Alert after 2 hours of continuous flow; High Flow Alert at 5+ gpm for 15+ minutes. Expected Usage suppresses alerts for a known pattern but still fires on changes or runs over 24 hours.
- Detail+ classifies use by fixture type (toilet, shower, irrigation, softener, and so on) from flow signatures. It cannot tell two toilets apart, and overlapping events get mislabeled.
- Rebates come through partner utilities; check flumewater.com/rebate by address. Homeowner insurers sometimes discount or give units away.
- A metal meter-pit lid weakens the sensor-to-bridge link; place the bridge in the room nearest the meter.

## Drip arithmetic

- One drop per second is about 1 gallon per day, about 0.0008 gpm.
- At 0.01-gallon meter resolution, that drip moves the last digit roughly every 13 minutes.
- Continuous flow of 0.2 gpm is about 290 gallons per day, about 8,600 gallons per month.
