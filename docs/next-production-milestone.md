# Next production milestone (live product)

**Status:** Locked  
**Context:** First nail salon owner has been using Vremio in production for ~1 month. Optimize this salon so the next business inherits solid schedule truth.

## Product answers (locked)

1. **#1 friction:** Slot gaps + **base service + add-ons** duration/availability behavior.
2. **Goal:** Deepen this salon first so the next salon is “good enough” out of the gate.

## Rejected candidates (do not build)

- Auto-open prepared message after approve/reject — emails already work; not wanted.
- “Phone-first remind loop” as the main milestone — reminder emails already work.

## Ops note (related, not the milestone)

Auto-complete **code exists** (`auto_complete_past_bookings`) but was missing from the Railway cron start command. Cron now includes it in `backend/railway.cron.toml`. Redeploy/restart the cron service so past **Approved** bookings become **Completed** after `end_at` + grace hours.

---

## Locked milestone

**Schedule truth: base + add-ons durations and slot gaps**

Make customer booking and owner calendar agree on how long a visit really takes when someone picks a base service plus add-ons, and how gaps between services/bookings apply — so wrong available times stop being the main friction.

### Ship criteria

1. Price-list lines can be marked **Add-on** in owner dashboard / admin (`is_addon`, default off — current menus unchanged).
2. Customer step 1: bases stay visible; optional extras appear **after** a base is chosen (reveal-after-base).
3. Choosing base + add-on(s) uses correct total duration for slots (addon minutes add on; `0` does not inherit full parent duration).
4. Booking saves base + add-on lines; schedule does not insert service-gap between a base and its extras.
5. Gap minutes between different services (e.g. manicure block vs pedicure) still **on hold** until the owner answers.
6. Live owner can mark French / drawings / extra length as add-ons when ready.

### Done so far

- `ServicePriceItem.is_addon` + migration `0026`
- Owner modal toggle + badge
- Booking UI reveal-after-base
- Duration / submit / slot map support for `{base, addons}`

### Still open

- Owner confirmation of exact gap rules
- Optional second UI variant (always-visible greyed extras)
- Add to calendar (approved only) — separate small ship
