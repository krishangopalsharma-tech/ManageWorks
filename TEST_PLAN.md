# ManageWorks — Detailed Test Plan

**Date:** 2026-05-28  
**Scope:** Full stack (Django REST + Vue 3) — all 13 backend apps, 18 frontend views  
**Source:** Derived from graphify graph (1,544 nodes · 3,072 edges) + code inspection  
**Priority basis:** Graphify god-node edge counts (most connected = highest failure blast radius)

---

## 1. Tech Stack to Install

No tests exist today. Install these before writing any test:

### Backend
```bash
cd backend
venv/bin/pip install pytest-django pytest factory-boy freezegun
```
Create `backend/pytest.ini`:
```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings.dev
python_files = tests.py test_*.py *_test.py
```

### Frontend
```bash
cd frontend
npm install --save-dev vitest @vue/test-utils @vitejs/plugin-vue jsdom
```
Add to `frontend/vite.config.js`:
```js
test: { environment: 'jsdom', globals: true }
```

### E2E
```bash
cd frontend
npm install --save-dev @playwright/test
npx playwright install chromium
```
Use `/qa` skill (gstack) for exploratory browser sessions against the live dev server.

---

## 2. Priority Map (from graphify god-nodes)

| Priority | Area | Why |
|---|---|---|
| P0 | Auth + RBAC | Gate for everything; wrong role = wrong data |
| P0 | Work model CRUD | 154 edges — most connected node in system |
| P1 | Notification signals | 6 signal types, Django pre/post_save chain |
| P1 | SiteRegisterThread | 46 edges; drives notifications + Telegram |
| P1 | WorkItem / WorkItemEntry | 118 / 46 edges; drives progress + MB details |
| P2 | MB Details | PDF import + measurement records |
| P2 | Item Progress | Consignee's primary read view |
| P2 | Dashboard | Summary stats, trend charts |
| P3 | Installation Certificate | PDF generation |
| P3 | Telegram bot | Complex state machine, external dep |
| P3 | Settings pages | Admin-only, lower failure impact |

---

## 3. Backend Tests

### 3.1 Auth & User Management (`users` app) — P0

**File:** `backend/users/tests.py`

| Test | What to verify |
|---|---|
| `test_login_valid` | POST `/api/auth/login/` with correct hrms_id + password → 200, session cookie set |
| `test_login_wrong_password` | → 400 |
| `test_login_inactive_user` | Revoked user → 403 |
| `test_logout` | POST `/api/auth/logout/` → clears session |
| `test_register` | POST `/api/auth/register/` → creates User + UserProfile (pending) |
| `test_me_unauthenticated` | GET `/api/auth/me/` → 401 |
| `test_me_authenticated` | → 200, returns role, hrms_id, is_staff |
| `test_approve_user_admin_only` | Non-admin POST `/api/auth/approve/<id>/` → 403 |
| `test_approve_user` | Admin approves pending user → is_active=True |
| `test_reject_user` | Admin rejects → User deleted |
| `test_update_role` | Admin PATCH role → UserProfile updated |
| `test_revoke_user` | Admin revoke → is_active=False |
| `test_forgot_password_unknown_hrms` | → 404 |

**Role matrix to verify on every protected endpoint:**
- `is_staff=True` (admin): full access
- `role=consignee`: own-work data only
- `role=observer/executor`: read-only or blocked
- Unauthenticated: 401

---

### 3.2 Work Model — P0

**File:** `backend/works/tests.py` (create new)

| Test | What to verify |
|---|---|
| `test_work_create` | Work.objects.create() saves all fields |
| `test_work_str` | `__str__` returns loa_number — contractor_name |
| `test_work_item_cascade` | Deleting Work deletes WorkItems |
| `test_work_extension` | Extension ordering by created_at |
| `test_hrms_id_nullable` | Work can exist without hrms_id |
| `test_work_item_entry_supply_type` | entry_type choices enforced |
| `test_work_item_entry_execution_location` | location field saved correctly |
| `test_electrical_parameters_json` | JSONField accepts list of {param, limit, result} |

---

### 3.3 Notification Signals — P1

**File:** `backend/notifications/tests.py`

| Test | Signal tested |
|---|---|
| `test_new_sr_notif_created` | Create SiteRegisterThread → admin + consignee get `new_sr` notification |
| `test_new_sr_no_hrms` | Work with no hrms_id → only admins notified |
| `test_ss_entry_notif` | Create WorkItemEntry (supply category) → `ss_entry` notif |
| `test_si_entry_notif` | Create WorkItemEntry (supply_installation) → `si_entry` notif |
| `test_ee_entry_notif` | Create WorkItemEntry (execution) → `ee_entry` notif |
| `test_unknown_category_no_notif` | WorkItemEntry with no category → no notification created |
| `test_financial_notif` | Create MBRecord → `financial` notif to admin + consignee |
| `test_financial_notif_date_str` | MBRecord with measurement_date → body includes formatted date |
| `test_loa_unassigned_notif` | Change Work.hrms_id → old consignee gets `loa_unassigned` |
| `test_loa_unassigned_new_work` | New Work created with hrms_id → NO unassign notif |
| `test_loa_unassigned_same_hrms` | hrms_id unchanged on save → NO notif |
| `test_loa_unassigned_user_not_found` | hrms_id → no matching User → no crash, no notif |
| `test_sr_thread_update_no_notif` | Updating existing SiteRegisterThread → NO duplicate notif |
| `test_notif_mark_read` | POST `/api/notifications/<id>/read/` → is_read=True |
| `test_notif_mark_all_read` | POST `/api/notifications/` → all user notifs marked read |
| `test_notif_list_own_only` | Consignee only sees own notifications |
| `test_notif_list_limit` | Returns at most 60 notifications |

---

### 3.4 Site Register — P1

**File:** `backend/site_register/tests.py`

| Test | What to verify |
|---|---|
| `test_sr_access_admin` | GET `/api/site-register/<work_id>/` as admin → 200 |
| `test_sr_access_consignee_own_work` | Consignee with matching hrms_id → 200 |
| `test_sr_access_consignee_other_work` | Consignee with different hrms_id → 403 |
| `test_sr_access_unauthenticated` | → 401 |
| `test_sr_number_format` | SiteRegisterThread.sr_number property → correct format |
| `test_loa_parties_list` | GET `/api/site-register/loa-parties/` → list of works |
| `test_supervisor_invite_create` | POST invite → creates SupervisorInvite with LOA ids |
| `test_supervisor_invite_expired` | is_expired() returns True after 48h (use freezegun) |
| `test_rly_linked_users_list` | GET `/api/site-register/rly-linked/` → list of RlyTelegramLink |
| `test_telegram_otp_generate` | GET OTP endpoint → creates TelegramLinkOTP |
| `test_telegram_otp_expired` | is_expired() returns True after expiry (freezegun) |
| `test_telegram_unlink` | DELETE → removes TelegramUserLink |

---

### 3.5 MB Details — P2

**File:** `backend/mb_details/tests.py`

| Test | What to verify |
|---|---|
| `test_mb_record_list` | GET `/api/mb-details/<work_id>/` → paginated records |
| `test_mb_record_create_admin_blocked` | Admin cannot create MB record (block_admin_write) |
| `test_mb_record_create_consignee` | Consignee on own work → 201 |
| `test_mb_record_delete` | DELETE → removes record |
| `test_mb_record_patch_amount` | PATCH amount → updates field |
| `test_mb_summary` | GET `/api/mb-details/<work_id>/summary/` → aggregated numbers |
| `test_pdf_import_valid` | POST PDF with valid MB data → records created |
| `test_pdf_import_invalid_format` | Bad PDF → 400 with meaningful error |
| `test_check_work_access_consignee_other` | Consignee on other work → 403 |
| `test_normalize_unit` | `normalize_unit('Nos')` → canonical form |
| `test_normalize_serial` | `normalize_serial('A.1.1')` → consistent key |

---

### 3.6 Dashboard — P2

**File:** `backend/dashboard/tests.py`

| Test | What to verify |
|---|---|
| `test_dashboard_stats_admin` | GET `/api/dashboard/` as admin → all works in stats |
| `test_dashboard_stats_consignee` | → only assigned works |
| `test_dashboard_trend_daily` | GET `/api/dashboard/trend/?period=daily&loa_id=X` → list of daily points |
| `test_dashboard_trend_invalid_period` | `period=hourly` → 400 |

---

### 3.7 Item Progress — P2

**File:** `backend/item_progress/tests.py`

| Test | What to verify |
|---|---|
| `test_item_progress_list_consignee` | Returns only items for consignee's works |
| `test_item_progress_search` | `?q=LOA-001` filters correctly |
| `test_progress_supply_qty` | supplied_quantity correctly reflected |
| `test_progress_execution_qty` | executed_quantity correctly reflected |

---

### 3.8 Add Work / Google Sheet — P2

**File:** `backend/add_work/tests.py`

| Test | What to verify |
|---|---|
| `test_sheet_id_from_url` | Extracts GSheet ID from various URL formats |
| `test_upload_work_admin_only` | Non-admin POST → 403 |
| `test_upload_work_creates_work_items` | Valid sheet data → Work + WorkItems created |
| `test_parse_response_handles_missing_cols` | Missing columns → graceful fallback |

---

### 3.9 Installation Certificate — P3

| Test | What to verify |
|---|---|
| `test_cert_generate` | POST → GeneratedCertificate created |
| `test_cert_auto_number` | `_auto_cert_number()` increments correctly |
| `test_cert_pdf_response` | GET cert PDF → Content-Type: application/pdf |

---

## 4. Frontend Tests

### 4.1 Router Guards

**File:** `frontend/src/router/router.test.js`

| Test | What to verify |
|---|---|
| `test_unauthenticated_redirects_login` | Visiting `/` unauthenticated → redirects to `/login` |
| `test_authenticated_login_redirects_home` | Authenticated user visits `/login` → redirected to `/` |
| `test_admin_only_blocks_non_admin` | `role=consignee` visits `/settings/user-management` → redirected to `/` |
| `test_site_register_consignee_allowed` | `role=consignee` visits `/site-register` → allowed |
| `test_site_register_observer_blocked` | `role=observer` visits `/site-register` → blocked |
| `test_public_routes_no_auth` | `/login`, `/register`, `/forgot-password` accessible without auth |

---

### 4.2 useNotifications Composable

**File:** `frontend/src/composables/useNotifications.test.js`

| Test | What to verify |
|---|---|
| `test_fetchNotifications_sets_state` | fetch returns data → `notifications` and `unreadCount` updated |
| `test_fetchNotifications_network_error` | fetch throws → state unchanged, no crash |
| `test_markRead_updates_local_state` | `markRead(id)` → matching notification.is_read = true, unreadCount-- |
| `test_markAllRead` | `markAllRead()` → all notifications.is_read = true, unreadCount = 0 |
| `test_notifConfig_known_type` | `notifConfig('new_sr')` → returns correct label/color |
| `test_notifConfig_unknown_type` | `notifConfig('unknown')` → returns fallback gray config |
| `test_polling_starts_stops` | `startPolling()` → interval set; `stopPolling()` → interval cleared |

---

### 4.3 Notifications.vue

**File:** `frontend/src/views/Notifications.test.js`

| Test | What to verify |
|---|---|
| `test_empty_state_shown` | `notifications = []` → renders "No notifications yet" |
| `test_admin_sees_all_6_columns` | `isAdmin=true`, all types empty → 6 columns rendered |
| `test_consignee_sees_only_populated` | `isAdmin=false`, only new_sr has data → 1 column |
| `test_unread_badge_count` | 3 unread in column → badge shows "3" |
| `test_read_card_lower_opacity` | `is_read=true` → card has opacity 0.7 |
| `test_unread_card_indicator_bar` | `is_read=false` → left indicator bar rendered |
| `test_handleClick_marks_read` | Click unread card → `markRead` called |
| `test_handleClick_routes_new_sr` | Click new_sr card → router pushes `/site-register` |
| `test_handleClick_routes_financial` | Click financial card → router pushes `/mb-details` |
| `test_handleClick_routes_default` | Click ss_entry card → router pushes `/item-progress` |
| `test_relativeTime_just_now` | diff < 1min → "just now" |
| `test_relativeTime_minutes` | 5min diff → "5m ago" |
| `test_relativeTime_hours` | 3hr diff → "3h ago" |
| `test_relativeTime_days` | 2day diff → "2d ago" |
| `test_relativeTime_date` | > 7days → formatted date |
| `test_mark_all_read_button_hidden` | `unreadCount=0` → button not rendered |

---

### 4.4 useAuth Composable

| Test | What to verify |
|---|---|
| `test_fetchMe_sets_authenticated` | API returns authenticated=true → state.authenticated=true |
| `test_fetchMe_unauthenticated` | API returns authenticated=false → state.user=null |
| `test_login_sets_state` | `login()` success → state.user set |
| `test_logout_clears_state` | `logout()` → state.user=null, authenticated=false |

---

### 4.5 Sidebar.vue

| Test | What to verify |
|---|---|
| `test_admin_menu_items_visible` | `is_staff=true` → Settings menu items shown |
| `test_non_admin_settings_hidden` | `role=consignee` → admin-only items hidden |
| `test_collapse_toggle` | Click collapse → sidebar collapses, tooltips appear |
| `test_active_route_highlight` | Current route → nav item highlighted |

---

## 5. E2E / Integration Tests (Playwright)

**File:** `frontend/e2e/`

Run against dev server (`npm run dev` + `python manage.py runserver`).

### 5.1 Authentication Flow

```
1. Visit http://localhost:5173 → redirected to /login
2. Login with wrong password → error message shown
3. Login with valid admin credentials → redirected to /
4. Visit /login while authenticated → redirected to /
5. Logout → redirected to /login
```

### 5.2 Admin: Add Work (Google Sheet)

```
1. Login as admin
2. Navigate to Add New Work
3. Paste Google Sheet URL
4. Submit → Work + WorkItems created
5. Navigate to Work Details → verify LOA number appears
```

### 5.3 Admin: Assign LOA to Consignee

```
1. Login as admin
2. Go to Work Details for a LOA
3. Set hrms_id to consignee's HRMS ID → save
4. Login as consignee → Dashboard shows that LOA
5. Check Notifications → no loa_unassigned notification (it's assignment, not unassignment)
```

### 5.4 Admin: Unassign LOA → Consignee Gets Notification

```
1. Work has hrms_id = consignee's ID
2. Admin changes hrms_id to different user (or clears it)
3. Login as old consignee
4. Visit /notifications → loa_unassigned notification appears
```

### 5.5 Consignee: Item Progress View

```
1. Login as consignee with assigned work
2. Visit /item-progress
3. Verify only own-work items shown
4. Search by LOA number → filtered results
5. Open item → WorkItemEntry form → submit supply entry
6. Check /notifications → ss_entry notification appears for admin + self
```

### 5.6 Site Register Flow

```
1. Login as admin
2. Visit /site-register
3. Select a LOA → thread list loads
4. Add new SR entry (Progress Update category)
5. Verify notification created (new_sr type)
6. Login as consignee for that LOA → sees the same SR thread
7. Observer/executor → redirected away from /site-register
```

### 5.7 MB Details Flow

```
1. Login as consignee
2. Visit /mb-details
3. Search LOA → select work
4. Add MB record → financial notification fires (check as admin)
5. Edit amount on existing record
6. Delete a record
7. View summary → totals match records
8. Upload PDF → verify parsing creates records
```

### 5.8 Notifications Multi-Column Layout

```
1. Login as admin (has all 6 columns)
2. Visit /notifications
3. Verify 6 columns rendered with correct color themes
4. Unread count badge visible on columns with unread items
5. Click "Mark all read" → all badges disappear, button hides
6. Click a notification card → marks read + navigates correctly
7. Login as consignee with only site register notifications
8. Visit /notifications → only new_sr column visible (no empty columns)
```

### 5.9 Dark Mode (regression)

```
1. Toggle dark mode in app
2. Navigate to /notifications → verify color variables render (no hardcoded colors)
3. Navigate to /site-register → same check
4. Navigate to /dashboard → same check
```

### 5.10 Installation Certificate

```
1. Login as user with access
2. Visit /installation-certificate
3. Select LOA + WorkItem entry
4. Generate certificate → PDF downloads or opens
5. Certificate number auto-increments on second generation
```

---

## 6. Telegram Bot Tests (Manual + Unit)

The bot has no easy automated test harness (requires Telegram API). Do these:

### Unit tests (mock `_api()`)

| Test | What to verify |
|---|---|
| `test_answer_callback_ack` | `answer_callback()` calls `answerCallbackQuery` API |
| `test_parse_date_valid` | `parse_date('01-06-2026')` → correct datetime |
| `test_parse_date_invalid` | `parse_date('not-a-date')` → None, no crash |
| `test_otp_expired` | `TelegramLinkOTP.is_expired()` with freezegun past expiry |
| `test_supervisor_invite_expired` | Same for `SupervisorInvite` |

### Manual checklist

- [ ] `/start` → shows correct entry menu
- [ ] OTP flow: generate OTP in app → send to bot → account linked
- [ ] Consignee bot: view assigned works
- [ ] SR attachment forwarding: admin sends doc → consignee receives
- [ ] Bot gracefully handles Telegram API timeout

---

## 7. Security Tests

| Check | How |
|---|---|
| CSRF enforced on all POST/PATCH/DELETE | Remove csrftoken cookie → expect 403 |
| Session fixation | Session ID changes after login |
| Insecure direct object reference | Consignee A GETs MB record belonging to Consignee B → 403 |
| Admin-only endpoints | All `/api/auth/approve/`, `/api/auth/revoke/`, `/api/add-work/` require is_staff |
| Notification isolation | Consignee only receives notifs for works where `work.hrms_id == user.username` |
| Site Register isolation | Consignee cannot read SR threads for unassigned LOAs |

Use the `/security-review` gstack skill for a deeper automated scan.

---

## 8. Regression Checklist (run before every deploy)

- [ ] Login → Dashboard loads, stats visible
- [ ] Work Details → LOA search works
- [ ] Item Progress → supply/execution entries submit
- [ ] MB Details → record create + summary correct
- [ ] Site Register → SR thread visible, attachment works
- [ ] Notifications → multi-column grid renders, mark-read works
- [ ] Dark mode toggle → no color breakage
- [ ] Telegram link flow → OTP generates and links
- [ ] PDF generation (Installation Cert) → file downloads

---

## 9. Test File Locations

```
backend/
  users/tests.py           ← auth + RBAC
  works/tests.py           ← Work, WorkItem, WorkItemEntry models
  notifications/tests.py   ← signal tests + API tests  ← HIGHEST VALUE, DO FIRST
  site_register/tests.py   ← SR access + OTP
  mb_details/tests.py      ← CRUD + PDF parser
  dashboard/tests.py       ← stats + trend
  item_progress/tests.py   ← list + search
  add_work/tests.py        ← GSheet import
  installation_cert/tests.py

frontend/src/
  composables/useNotifications.test.js
  composables/useAuth.test.js
  views/Notifications.test.js
  views/Login.test.js
  router/router.test.js
  components/Sidebar.test.js

frontend/e2e/
  auth.spec.js
  notifications.spec.js
  site-register.spec.js
  mb-details.spec.js
  item-progress.spec.js
  installation-cert.spec.js
```

---

## 10. Suggested Execution Order

1. **Install pytest-django** + write `notifications/tests.py` signal tests — biggest ROI, these signals have never been tested and cover 6 critical paths
2. **Write auth tests** — security foundation
3. **Write Work model tests** — 154-edge god node, most likely to break other things
4. **Install Vitest** + write `useNotifications.test.js` — already fully built composable, easy wins
5. **Write Notifications.vue component tests** — just refactored, highest regression risk
6. **Write router guard tests** — RBAC bugs are silent and dangerous
7. **Run `/qa` skill** against dev server for exploratory browser testing
8. **Add Playwright E2E** for the 3 critical paths: auth flow, SR flow, notifications flow
9. Remaining backend + frontend unit tests
10. Security checklist manually

---

## 11. Run Commands

```bash
# Backend
cd backend
venv/bin/pytest notifications/tests.py -v          # notifications only
venv/bin/pytest --tb=short                          # all

# Frontend unit
cd frontend
npm run test                                        # Vitest watch
npm run test -- --run                               # CI mode

# E2E
cd frontend
npx playwright test                                 # all specs
npx playwright test e2e/notifications.spec.js       # one spec
npx playwright test --headed                        # watch browser
```
