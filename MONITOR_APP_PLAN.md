# MonitorWorks — Master Monitoring App Plan

**Purpose:** Higher officials (Mumbai HQ) monitor works across multiple divisions (ADI, RTM, BRC, etc.) on intranet. Read-only aggregator fed by ManageWorks instances at each division.

---

## Architecture Overview

```
[ManageWorks - ADI]  ──API──┐
[ManageWorks - RTM]  ──API──┤──► [MonitorWorks - Mumbai HQ] ──► Higher Officials
[ManageWorks - BRC]  ──API──┘         (read-only, intranet)
         ...
```

Each division runs its own ManageWorks instance. MonitorWorks pulls data from all of them and presents a unified view.

---

## Approach Options

### Option A — Direct Pull (Simpler)
Monitor calls each division's ManageWorks API directly, on page load.

| Pros | Cons |
|---|---|
| No local DB needed | Division server down = blank data |
| Always fresh data | Mumbai server needs route to all division IPs |
| Less code | Slow if many divisions |

### Option B — Pull + Local Cache (Recommended)
Monitor pulls from each ManageWorks every 5–15 minutes, stores in its own local DB. Pages served from cache.

| Pros | Cons |
|---|---|
| Division down = last known data still shows | Slight delay (5–15 min, acceptable for monitoring) |
| Fast page loads | More setup (cron job or Celery) |
| Historical snapshots possible | |
| One network failure doesn't break everything | |

**Recommendation: Option B.** For government railway monitoring, resilience > real-time.

---

## Part 1 — Changes Required in ManageWorks (Each Division)

### 1.1 New Model — MonitorApiKey

```python
# backend/monitor_access/models.py
class MonitorApiKey(models.Model):
    key        = models.CharField(max_length=64, unique=True)
    label      = models.CharField(max_length=100)   # e.g. "Mumbai HQ Monitor"
    created_at = models.DateTimeField(auto_now_add=True)
    is_active  = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.key:
            import secrets
            self.key = secrets.token_hex(32)
        super().save(*args, **kwargs)
```

### 1.2 Flag on Work Model

```python
# Add to works/models.py → Work model
shared_to_monitor = models.BooleanField(default=False)
```

Admin can toggle per work which ones are visible to MonitorWorks.

### 1.3 New Read-Only API Endpoints

All require `X-Api-Key: <key>` header. If key missing/invalid → 403.

```
GET /api/monitor/dashboard/
    → Division-level summary stats
    {
      "division": "ADI",
      "total_shared_works": 24,
      "avg_supply_pct": 67.2,
      "avg_execution_pct": 52.4,
      "avg_overall_pct": 59.8,
      "last_updated": "2026-05-30T10:30:00Z"
    }

GET /api/monitor/works/
    → List of shared works (basic fields)
    [
      {
        "id": 1,
        "loa_number": "ADI/TELE/...",
        "name_of_work": "...",
        "contractor_name": "...",
        "consignee": "SSE/TELE/ADI/Store",
        "date_of_completion": "2026-12-31",
        "supply_pct": 67.0,
        "execution_pct": 52.0,
        "overall_pct": 59.5,
        "financial_pct": 45.0
      },
      ...
    ]

GET /api/monitor/works/{id}/
    → Full work detail (same as WorkDetails page data, read-only)
```

### 1.4 ManageWorks Admin UI Changes

In ManageWorks Settings page, add two new sections:

**Monitor API Keys**
- Generate new key (button → shows key once)
- List active keys with label + created date
- Revoke key button

**Shared Works**
- Table of all works with toggle switch `Share to Monitor`
- Bulk select option

---

## Part 2 — MonitorWorks App (New Project)

Same tech stack as ManageWorks: **Django (backend) + Vue 3 (frontend)**.

### 2.1 Project Structure

```
MonitorWorks/
  backend/
    config/
      settings/
        base.py
        dev.py
        prod.py
    divisions/          ← Division model, CRUD
    sync/               ← Pull task (cron), cache logic
    cached_data/        ← Local mirror models
    api/                ← Endpoints for Vue frontend
    manage.py
  frontend/
    src/
      views/
        Dashboard.vue
        WorkDetails.vue
        Settings.vue
      components/
        DivisionCard.vue
        WorkTable.vue
        ProgressBadge.vue
      router/index.js
      App.vue
```

### 2.2 Division Model (MonitorWorks DB)

```python
class Division(models.Model):
    name        = models.CharField(max_length=100)   # "Ahmedabad"
    short_code  = models.CharField(max_length=10)    # "ADI"
    base_url    = models.URLField()                  # http://100.87.146.36
    api_key     = models.CharField(max_length=64)
    last_sync   = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(max_length=20, default='pending')
                  # pending / success / error
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
```

### 2.3 Cached Work Model (MonitorWorks DB)

```python
class CachedWork(models.Model):
    division        = models.ForeignKey(Division, on_delete=models.CASCADE)
    remote_id       = models.IntegerField()          # ID in source ManageWorks
    loa_number      = models.CharField(max_length=200)
    name_of_work    = models.TextField()
    contractor_name = models.CharField(max_length=200)
    consignee       = models.CharField(max_length=200)
    date_of_completion = models.DateField(null=True)
    supply_pct      = models.FloatField(default=0)
    execution_pct   = models.FloatField(default=0)
    overall_pct     = models.FloatField(default=0)
    financial_pct   = models.FloatField(default=0)
    raw_data        = models.JSONField(default=dict)  # full detail snapshot
    synced_at       = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('division', 'remote_id')
```

### 2.4 Sync Task (runs every 10 minutes via cron or Celery)

```python
# sync/tasks.py
import requests

def sync_division(division):
    headers = {'X-Api-Key': division.api_key}
    try:
        r = requests.get(f'{division.base_url}/api/monitor/works/', headers=headers, timeout=10)
        r.raise_for_status()
        works = r.json()
        for w in works:
            CachedWork.objects.update_or_create(
                division=division,
                remote_id=w['id'],
                defaults={...}
            )
        division.last_sync = now()
        division.sync_status = 'success'
    except Exception as e:
        division.sync_status = 'error'
    division.save()
```

**Cron setup (simple, no Celery needed):**
```
*/10 * * * * cd /path/to/MonitorWorks && python manage.py sync_divisions
```

---

## Part 3 — Pages Design

### 3.1 Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│  MonitorWorks — Western Railway                    👤 DyCE/P    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Last synced: 2 min ago          [Refresh Now]                  │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  ADI        │  │  RTM        │  │  BRC        │  + more...   │
│  │  24 works   │  │  18 works   │  │  12 works   │              │
│  │             │  │             │  │             │              │
│  │ Supply  67% │  │ Supply  45% │  │ Supply  80% │              │
│  │ Exec    52% │  │ Exec    38% │  │ Exec    71% │              │
│  │ Overall 59% │  │ Overall 41% │  │ Overall 75% │              │
│  │             │  │             │  │             │              │
│  │ ⚠ 3 lagging │  │ ⚠ 5 lagging │  │ ✓ On track  │              │
│  │ [View Works]│  │ [View Works]│  │ [View Works]│              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                                                                 │
│  ── Combined Summary ──────────────────────────────────────     │
│  Total Works: 54 | Avg Supply: 64% | Avg Execution: 54%         │
│  Overall Progress: 59% | Financial: 48%                         │
│                                                                 │
│  ── Lagging Works (across all divisions) ──────────────────     │
│  [Table: Works where progress < expected based on due date]     │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Work Details

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Back    Work Details — ADI Division                          │
├─────────────────────────────────────────────────────────────────┤
│  [Division Filter: ALL ▼]  [Search LOA / Work Name]            │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ LOA: ADI/TELE/25-26/001                           ADI   │   │
│  │ Work: Supply of NIM cards at Ahmedabad station           │   │
│  │ Contractor: ABC Pvt Ltd | Consignee: SSE/TELE/ADI       │   │
│  │ Due: 31 Dec 2026                                         │   │
│  │                                                          │   │
│  │  SUPPLY      EXECUTION    OVERALL     FINANCIAL          │   │
│  │  [  67%  ]  [  52%  ]   [  59%  ]   [  45%  ]          │   │
│  │                                                          │   │
│  │  [View Full Details ↗]   (opens read-only detail page)  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  (more work cards...)                                           │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Settings (Admin only)

```
┌─────────────────────────────────────────────────────────────────┐
│  Settings                                                       │
├─────────────────────────────────────────────────────────────────┤
│  ── Divisions ──────────────────────────────────────────────    │
│                                                                 │
│  Name    Code  URL                      Status    Last Sync     │
│  ──────  ────  ───────────────────────  ────────  ──────────    │
│  Ahmd.   ADI   http://100.87.146.36     ✓ OK      2 min ago     │
│  Ratlam  RTM   http://100.xx.xx.xx      ✓ OK      3 min ago     │
│  Vadora  BRC   http://100.xx.xx.xx      ✗ Error   45 min ago    │
│                                                                 │
│  [+ Add Division]                                               │
│                                                                 │
│  ── Monitor Users ──────────────────────────────────────────    │
│  (users who can login to MonitorWorks — separate from          │
│   ManageWorks users)                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 4 — Additional Ideas

### Idea 1 — Lagging Works Alert (High Value)
Auto-calculate expected progress based on contract start + end dates. If actual % is more than 15% below expected → mark as lagging. Show on dashboard without user having to dig.

```python
def is_lagging(work):
    from datetime import date
    today = date.today()
    start = work.date_of_loa or work.created_date
    end   = work.date_of_completion
    if not start or not end or end <= today:
        return False
    elapsed_ratio = (today - start).days / (end - start).days
    expected_pct  = elapsed_ratio * 100
    return work.overall_pct < (expected_pct - 15)
```

### Idea 2 — PDF Combined Report
One button on Dashboard → generates PDF with all divisions' progress. Useful for DyCE/P review meetings.

### Idea 3 — Same Django Project, Different App (Saves Infra)
Instead of a separate server in Mumbai, add a `monitor` Django app to each ManageWorks installation. Mumbai official logs in with role `monitor` and sees all divisions (ManageWorks calls out to other divisions). No new server needed. Simpler for intranet where one server can reach all others.

### Idea 4 — Telegram Push Instead of API Pull
Each ManageWorks sends updates to a shared Telegram group (bot) when significant changes happen (work assigned, supply entry, MB recorded). Monitor just reads that group. No API, no server. Ultra simple but less structured.

**Verdict:** Ideas 1 + 2 are must-have. Idea 3 is worth considering to avoid a new server.

---

## Part 5 — Implementation Phases

### Phase 1 — ManageWorks Changes (2–3 days)
- [ ] `MonitorApiKey` model + migration
- [ ] `Work.shared_to_monitor` field + migration
- [ ] `/api/monitor/dashboard/` endpoint
- [ ] `/api/monitor/works/` endpoint
- [ ] `/api/monitor/works/{id}/` endpoint
- [ ] API key auth middleware
- [ ] Admin UI: generate/revoke keys, toggle shared works

### Phase 2 — MonitorWorks App Skeleton (2–3 days)
- [ ] New Django project setup
- [ ] `Division` model + Settings API
- [ ] Vue 3 scaffold with router (Dashboard / WorkDetails / Settings)
- [ ] Settings page: add division, test connection

### Phase 3 — Sync + Dashboard (3–4 days)
- [ ] Sync management command (`sync_divisions`)
- [ ] Cron setup
- [ ] Dashboard division cards
- [ ] Combined summary bar
- [ ] Lagging works detection + display

### Phase 4 — Work Details + Polish (2–3 days)
- [ ] Work Details page with division filter
- [ ] Full detail drill-down (read-only)
- [ ] Sync status indicator (last synced, error state)
- [ ] PDF combined report

### Phase 5 — Deployment
- [ ] Deploy MonitorWorks on Mumbai server (or any intranet server)
- [ ] Configure each division ManageWorks: generate API key, share works
- [ ] Add division entries in MonitorWorks Settings
- [ ] Test connectivity across divisions via Tailscale/intranet

---

## Quick Decision Checklist

Before starting, decide:

1. **Separate server in Mumbai or same project?**
   - Separate = cleaner, more control, needs one more server
   - Same project = simpler infra, less work

2. **Option A (direct pull) or Option B (cached sync)?**
   - Recommended: Option B (cached)

3. **Celery or simple cron for sync?**
   - Recommended: Simple cron (`*/10 * * * *`) — no Redis/Celery overhead needed

4. **Which divisions to support at launch?**
   - Start with ADI only, add RTM/BRC after testing

5. **Who can log into MonitorWorks?**
   - Separate user accounts (DyCE/P, Sr.DEN, etc.) created by MonitorWorks admin
   - Not linked to ManageWorks user accounts

---

*Plan created: 2026-05-30*
*Project: ManageWorks — Western Railway*
