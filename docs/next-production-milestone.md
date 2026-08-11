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

1. Choosing base + add-on(s) uses the **correct total duration** for slot search (price-item durations where set; otherwise parent service).
2. **Service gap** policy applies in the way this salon expects (between services in one booking and/or between bookings — confirm with owner once, then encode it).
3. Owner add/edit booking keeps the same duration rules (no silent drop back to base-only duration).
4. Tests cover the salon’s real cases (e.g. manicure + design add-on).
5. Live owner confirms available times match how she actually works for one busy week.

### Out of scope

- Second-salon onboarding packaging
- Auto message modal
- Deposits / loyalty / multi-staff

### Next step when building

Plan the exact gap + add-on rules with a short owner confirmation, then implement in `services.py` slot engine + booking form + owner booking form, with tests.
