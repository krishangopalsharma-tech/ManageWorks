# Graph Report - .  (2026-05-06)

## Corpus Check
- Large corpus: 244 files · ~201,146 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 1049 nodes · 1855 edges · 46 communities detected
- Extraction: 72% EXTRACTED · 28% INFERRED · 0% AMBIGUOUS · INFERRED: 519 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_jQuery Core Library|jQuery Core Library]]
- [[_COMMUNITY_Django Backend Routing|Django Backend Routing]]
- [[_COMMUNITY_Django Admin Popups|Django Admin Popups]]
- [[_COMMUNITY_Bootstrap & jQuery Bundles|Bootstrap & jQuery Bundles]]
- [[_COMMUNITY_jQuery Minified|jQuery Minified]]
- [[_COMMUNITY_Work Detail API|Work Detail API]]
- [[_COMMUNITY_DRF API Views|DRF API Views]]
- [[_COMMUNITY_URL & Text Utilities|URL & Text Utilities]]
- [[_COMMUNITY_Django Admin Assets|Django Admin Assets]]
- [[_COMMUNITY_LOA Dashboard Pipeline|LOA Dashboard Pipeline]]
- [[_COMMUNITY_MB Details Vue Component|MB Details Vue Component]]
- [[_COMMUNITY_XRegExp Prettify Minified|XRegExp Prettify Minified]]
- [[_COMMUNITY_Google Sheets Ingestion|Google Sheets Ingestion]]
- [[_COMMUNITY_Vue Router & Views|Vue Router & Views]]
- [[_COMMUNITY_Python Dependencies|Python Dependencies]]
- [[_COMMUNITY_Django App Configs|Django App Configs]]
- [[_COMMUNITY_Frontend Icons & Assets|Frontend Icons & Assets]]
- [[_COMMUNITY_Select2 Minified|Select2 Minified]]
- [[_COMMUNITY_PDF Parser Utilities|PDF Parser Utilities]]
- [[_COMMUNITY_Sidebar Navigation|Sidebar Navigation]]
- [[_COMMUNITY_Measurement Book Parser|Measurement Book Parser]]
- [[_COMMUNITY_Django Admin Actions|Django Admin Actions]]
- [[_COMMUNITY_MB Details Search API|MB Details Search API]]
- [[_COMMUNITY_DRF Static Assets|DRF Static Assets]]
- [[_COMMUNITY_Initial Migrations|Initial Migrations]]
- [[_COMMUNITY_Theme Management|Theme Management]]
- [[_COMMUNITY_CSRF Exempt Auth|CSRF Exempt Auth]]
- [[_COMMUNITY_Django Entry Point|Django Entry Point]]
- [[_COMMUNITY_Role Migration|Role Migration]]
- [[_COMMUNITY_Work Extension Migration|Work Extension Migration]]
- [[_COMMUNITY_Work Item Challan Migration|Work Item Challan Migration]]
- [[_COMMUNITY_Work Consignee Migration|Work Consignee Migration]]
- [[_COMMUNITY_Work Item Update Migration|Work Item Update Migration]]
- [[_COMMUNITY_Entry Type Migration|Entry Type Migration]]
- [[_COMMUNITY_Inspection Date Migration|Inspection Date Migration]]
- [[_COMMUNITY_Work Item Entry Migration|Work Item Entry Migration]]
- [[_COMMUNITY_Drop WorkBill Migration|Drop WorkBill Migration]]
- [[_COMMUNITY_MB Record Migration|MB Record Migration]]
- [[_COMMUNITY_WSGI Config|WSGI Config]]
- [[_COMMUNITY_ASGI Config|ASGI Config]]
- [[_COMMUNITY_Django Project Settings|Django Project Settings]]
- [[_COMMUNITY_Name Of Work Migration|Name Of Work Migration]]
- [[_COMMUNITY_Receive Note Migration|Receive Note Migration]]
- [[_COMMUNITY_Measurement Date Migration|Measurement Date Migration]]
- [[_COMMUNITY_HRMS ID Migration|HRMS ID Migration]]
- [[_COMMUNITY_Project CLAUDE|Project CLAUDE.md]]

## God Nodes (most connected - your core abstractions)
1. `Work` - 89 edges
2. `WorkItem` - 74 edges
3. `MBItem` - 42 edges
4. `MBRecord` - 40 edges
5. `WorkItemEntry` - 34 edges
6. `MBRecordSerializer` - 34 edges
7. `WorkExtension` - 30 edges
8. `Django Admin UI` - 27 edges
9. `WorkItemEntrySerializer` - 26 edges
10. `ManageWorks Backend` - 25 edges

## Surprising Connections (you probably didn't know these)
- `ManageWorks Favicon - Gear/Settings Icon with Checkmark` --conceptually_related_to--> `Django Admin UI`  [AMBIGUOUS]
  frontend/public/favicon.svg → backend/staticfiles/admin/img/README.md
- `Vue 3 + Vite Frontend` --semantically_similar_to--> `LOA 38264 Marvel Telecom Progress Dashboard`  [INFERRED] [semantically similar]
  frontend/README.md → fff/README.md
- `clean_str()` --calls--> `parse_and_save_work_excel()`  [INFERRED]
  fff/build_data.py → backend/add_work/services/excel_parser.py
- `Admin Icon: Unknown/Question Mark (circle-question, white fill)` --conceptually_related_to--> `Django Admin UI`  [INFERRED]
  backend/staticfiles/admin/img/icon-unknown-alt.svg → backend/staticfiles/admin/img/README.md
- `Admin Icon: View Link (eye icon, blue fill)` --conceptually_related_to--> `Django Admin UI`  [INFERRED]
  backend/staticfiles/admin/img/icon-viewlink.svg → backend/staticfiles/admin/img/README.md

## Hyperedges (group relationships)
- **Marvel LOA 38264 Dashboard Data Pipeline** — fff_readme_source_xlsx, fff_readme_build_data_py, fff_readme_data_json, fff_readme_dashboard_html [EXTRACTED 0.95]
- **KPI Financial Metrics Cluster** — fff_readme_kpi_strip, fff_readme_weighted_progress, fff_readme_rebate_rate, fff_readme_baseline_reconciliation [INFERRED 0.85]
- **Schedule A and B Progress Split** — fff_readme_schedule_a, fff_readme_schedule_b, fff_readme_material_supply_progress, fff_readme_execution_progress [EXTRACTED 0.95]

## Communities

### Community 0 - "jQuery Core Library"
Cohesion: 0.04
Nodes (55): addCombinator(), adoptValue(), ajaxConvert(), ajaxHandleResponses(), Animation(), assert(), boxModelAdjustment(), buildFragment() (+47 more)

### Community 1 - "Django Backend Routing"
Cohesion: 0.08
Nodes (60): DashboardStatsView, ProgressTrendView, GET /api/dashboard/trend/?period=daily|weekly|monthly|yearly&loa_id=<id>     Onl, GET /api/dashboard/trend/?period=daily|weekly|monthly|yearly&loa_id=<id>     Onl, ItemSearchView, GET /api/item-progress/search/?q=cable&work_ids=1,2,3     Returns WorkItems matc, GET /api/item-progress/works/ — lightweight work list for the dropdown., WorkListView (+52 more)

### Community 2 - "Django Admin Popups"
Cohesion: 0.03
Nodes (27): addPopupIndex(), dismissAddRelatedObjectPopup(), dismissChangeRelatedObjectPopup(), dismissDeleteRelatedObjectPopup(), dismissRelatedLookupPopup(), removePopupIndex(), showAdminPopup(), showRelatedObjectLookupPopup() (+19 more)

### Community 3 - "Bootstrap & jQuery Bundles"
Cohesion: 0.07
Nodes (50): Ye(), e(), i(), l(), n(), r(), s(), u() (+42 more)

### Community 4 - "jQuery Minified"
Cohesion: 0.09
Nodes (37): $(), A(), Ae(), B(), Be(), c(), $e(), ee() (+29 more)

### Community 5 - "Work Detail API"
Cohesion: 0.13
Nodes (36): _check_authenticated(), _check_can_modify_work(), _check_not_observer(), ParsePDFsView, PATCH /api/update-work/entries/<entry_id>/  – edit own submitted entry., PATCH /api/update-work/entries/<entry_id>/  – any non-observer may edit., PATCH /api/update-work/entries/<entry_id>/  – only submitter or admin may edit., Recompute and save supplied_quantity and executed_quantity from current entries. (+28 more)

### Community 6 - "DRF API Views"
Cohesion: 0.09
Nodes (24): APIView, DocumentGeneratorView, UserProfileAdmin, UserProfile, AllUsersView, ApproveUserView, AssignWorkView, _is_admin() (+16 more)

### Community 7 - "URL & Text Utilities"
Cohesion: 0.07
Nodes (27): downcode(), URLify(), _arrayLikeToArray(), augment(), buildAstral(), cacheAstral(), cacheInvertedBmp(), charCode() (+19 more)

### Community 8 - "Django Admin Assets"
Cohesion: 0.09
Nodes (39): Admin Calendar Navigation Icons Sprite (circle-chevron-left/right), Creative Commons Attribution 4.0 International (CC-BY-4.0), Django Admin UI, Font Awesome Free 6.7.2, Font Awesome Free 6.7.2 License (Fonticons Inc.), Admin Icon: Add Link (plus icon, green fill), Admin Icon: Alert Dark (triangle-exclamation dark variant), Admin Icon: Alert (triangle-exclamation) (+31 more)

### Community 9 - "LOA Dashboard Pipeline"
Cohesion: 0.08
Nodes (37): Baseline Reconciliation (3 Source Metrics), build_data.py Data Pipeline Script, Cross-Filtering Interactivity, LOA 38264 Marvel Telecom Progress Dashboard, dashboard.html Self-Contained Dashboard File, Data Cleaning Rules (build_data.py), data.json Cleaned Data Payload, Dashboard Design Notes (Colours, Typography) (+29 more)

### Community 10 - "MB Details Vue Component"
Cohesion: 0.11
Nodes (25): applyBulkPct(), closeEdit(), deleteRecord(), editRowAmount(), editRowIsValid(), fmtMbNum(), importPdf(), loadRecords() (+17 more)

### Community 11 - "XRegExp Prettify Minified"
Cohesion: 0.09
Nodes (19): B(), C(), D(), E(), L(), M(), u(), x() (+11 more)

### Community 12 - "Google Sheets Ingestion"
Cohesion: 0.1
Nodes (17): _download_google_sheet(), _parse_response(), Extract the spreadsheet ID from a Google Sheets sharing URL., Download a publicly shared Google Sheet as xlsx using curl., Convert parser result dict → (response_data, http_status)., _sheet_id_from_url(), UploadWorkView, clean_str() (+9 more)

### Community 13 - "Vue Router & Views"
Cohesion: 0.08
Nodes (3): initCharts(), initOneChart(), L()

### Community 14 - "Python Dependencies"
Cohesion: 0.13
Nodes (26): asgiref, certifi, cffi, charset-normalizer, cryptography, Django, django-cors-headers, djangorestframework (+18 more)

### Community 15 - "Django App Configs"
Cohesion: 0.11
Nodes (10): AddWorkConfig, AppConfig, DashboardConfig, DocumentsConfig, ItemProgressConfig, MbDetailsConfig, UpdateWorkConfig, UsersConfig (+2 more)

### Community 16 - "Frontend Icons & Assets"
Cohesion: 0.17
Nodes (19): Bluesky Social Icon, Discord Icon, Documentation Icon, ManageWorks Favicon - Gear/Settings Icon with Checkmark, Frontend Source Assets Directory, Frontend Public Assets Directory, GitHub Icon, Hero Image (Isometric Layered Shapes) (+11 more)

### Community 17 - "Select2 Minified"
Cohesion: 0.15
Nodes (8): b(), D(), e(), i(), o(), S(), u(), y()

### Community 18 - "PDF Parser Utilities"
Cohesion: 0.22
Nodes (14): _extract_text(), _normalize_serial(), _normalize_unit(), _parse_header(), _parse_item_block(), parse_rm_pdf(), PDF parser for IRWCMS-format Record Measurement (RM) MBs.  Extracts: MB number,, Parse an IRWCMS Record Measurement PDF.      Returns dict:       {         'head (+6 more)

### Community 19 - "Sidebar Navigation"
Cohesion: 0.17
Nodes (6): handleLogout(), authHeaders(), getCsrfToken(), login(), logout(), register()

### Community 20 - "Measurement Book Parser"
Cohesion: 0.22
Nodes (12): _clean_desc(), _clean_sno(), _lv_find(), _parse_date(), parse_receipt_pdf(), Strip trailing dashes, slashes, spaces from serial/item numbers., Strip surrounding quotes/smart-quotes and normalise whitespace., Extract label→value pairs from PDF tables (handles 2- and 4-column rows). (+4 more)

### Community 21 - "Django Admin Actions"
Cohesion: 0.38
Nodes (8): checker(), clearAcross(), hide(), reset(), show(), showClear(), showQuestion(), updateCounter()

### Community 22 - "MB Details Search API"
Cohesion: 0.47
Nodes (3): _base_queryset(), _items_queryset(), WorkSearchView

### Community 23 - "DRF Static Assets"
Cohesion: 0.47
Nodes (6): Django REST Framework UI Assets, Font Awesome Webfont SVG (REST Framework), Glyphicons Halflings PNG Sprite (REST Framework), Glyphicons Halflings Regular SVG Font (REST Framework), Glyphicons Halflings White PNG Sprite (REST Framework), REST Framework Grid PNG Image

### Community 25 - "Initial Migrations"
Cohesion: 0.5
Nodes (1): Migration

### Community 26 - "Theme Management"
Cohesion: 0.83
Nodes (3): cycleTheme(), initTheme(), setTheme()

### Community 28 - "CSRF Exempt Auth"
Cohesion: 0.5
Nodes (2): CsrfExemptSessionAuthentication, SessionAuthentication

### Community 29 - "Django Entry Point"
Cohesion: 0.67
Nodes (2): main(), Run administrative tasks.

### Community 33 - "Role Migration"
Cohesion: 0.67
Nodes (1): Migration

### Community 35 - "Work Extension Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 36 - "Work Item Challan Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 37 - "Work Consignee Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 38 - "Work Item Update Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 39 - "Entry Type Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 40 - "Inspection Date Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 41 - "Work Item Entry Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 42 - "Drop WorkBill Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 43 - "MB Record Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 44 - "WSGI Config"
Cohesion: 1.0
Nodes (1): WSGI config for config project.  It exposes the WSGI callable as a module-level

### Community 45 - "ASGI Config"
Cohesion: 1.0
Nodes (1): ASGI config for config project.  It exposes the ASGI callable as a module-level

### Community 46 - "Django Project Settings"
Cohesion: 1.0
Nodes (1): Django settings for config project.  Generated by 'django-admin startproject' us

### Community 47 - "Name Of Work Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 48 - "Receive Note Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 49 - "Measurement Date Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 61 - "HRMS ID Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 88 - "Project CLAUDE.md"
Cohesion: 1.0
Nodes (1): ManageWorks CLAUDE.md

## Ambiguous Edges - Review These
- `ManageWorks Favicon - Gear/Settings Icon with Checkmark` → `Django Admin UI`  [AMBIGUOUS]
  frontend/public/favicon.svg · relation: conceptually_related_to

## Knowledge Gaps
- **53 isolated node(s):** `Build the clean JSON payload for the Marvel LOA-38264 dashboard.`, `Convert NaN/NaT/numpy scalars to JSON-safe natives.`, `Run administrative tasks.`, `Meta`, `A single lot submission for a WorkItem.     entry_type='supply'    → full inspec` (+48 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Initial Migrations`** (4 nodes): `0001_initial.py`, `0001_initial.py`, `0001_initial.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `CSRF Exempt Auth`** (4 nodes): `authentication.py`, `CsrfExemptSessionAuthentication`, `.enforce_csrf()`, `SessionAuthentication`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Django Entry Point`** (3 nodes): `main()`, `manage.py`, `Run administrative tasks.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Role Migration`** (3 nodes): `0002_migrate_roles_to_consignee_admin.py`, `migrate_roles()`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Work Extension Migration`** (2 nodes): `0006_work_extension_bill.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Work Item Challan Migration`** (2 nodes): `0002_workitem_challan_no_workitem_supplied_quantity_and_more.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Work Consignee Migration`** (2 nodes): `0004_work_add_consignee.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Work Item Update Migration`** (2 nodes): `0003_workitem_updated_at_workitem_updated_by_userprofile.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Entry Type Migration`** (2 nodes): `0007_entry_type_location_remarks_executed_qty.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Inspection Date Migration`** (2 nodes): `0008_workitementry_date_of_inspection_and_more.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Work Item Entry Migration`** (2 nodes): `0005_workitementry.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Drop WorkBill Migration`** (2 nodes): `0009_drop_workbill.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `MB Record Migration`** (2 nodes): `0002_alter_mbrecord_mb_number.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `WSGI Config`** (2 nodes): `wsgi.py`, `WSGI config for config project.  It exposes the WSGI callable as a module-level`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `ASGI Config`** (2 nodes): `asgi.py`, `ASGI config for config project.  It exposes the ASGI callable as a module-level`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Django Project Settings`** (2 nodes): `settings.py`, `Django settings for config project.  Generated by 'django-admin startproject' us`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Name Of Work Migration`** (2 nodes): `0010_add_name_of_work.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Receive Note Migration`** (2 nodes): `0011_workitementry_receive_note_date.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Measurement Date Migration`** (2 nodes): `0003_add_measurement_date.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `HRMS ID Migration`** (2 nodes): `0012_add_hrms_id_and_inspection_agency.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Project CLAUDE.md`** (1 nodes): `ManageWorks CLAUDE.md`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `ManageWorks Favicon - Gear/Settings Icon with Checkmark` and `Django Admin UI`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `Q()` connect `Bootstrap & jQuery Bundles` to `Django Backend Routing`, `MB Details Search API`?**
  _High betweenness centrality (0.183) - this node is a cross-community bridge._
- **Why does `$()` connect `Django Admin Popups` to `Bootstrap & jQuery Bundles`?**
  _High betweenness centrality (0.161) - this node is a cross-community bridge._
- **Why does `matcher()` connect `jQuery Core Library` to `Django Admin Popups`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Are the 87 inferred relationships involving `Work` (e.g. with `WorkSearchView` and `WorkAdmin`) actually correct?**
  _`Work` has 87 INFERRED edges - model-reasoned connections that need verification._
- **Are the 72 inferred relationships involving `WorkItem` (e.g. with `WorkSearchView` and `WorkAdmin`) actually correct?**
  _`WorkItem` has 72 INFERRED edges - model-reasoned connections that need verification._
- **Are the 37 inferred relationships involving `MBItem` (e.g. with `Work` and `WorkItem`) actually correct?**
  _`MBItem` has 37 INFERRED edges - model-reasoned connections that need verification._