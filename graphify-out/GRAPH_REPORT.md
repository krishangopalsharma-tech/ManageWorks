# Graph Report - .  (2026-05-04)

## Corpus Check
- 239 files · ~50,000 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 941 nodes · 1580 edges · 39 communities detected
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 386 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Django REST API Layer|Django REST API Layer]]
- [[_COMMUNITY_jQuery Core Library|jQuery Core Library]]
- [[_COMMUNITY_Django Admin Popups|Django Admin Popups]]
- [[_COMMUNITY_BootstrapjQuery Bundle|Bootstrap/jQuery Bundle]]
- [[_COMMUNITY_Django App Registry|Django App Registry]]
- [[_COMMUNITY_jQuery Minified Build|jQuery Minified Build]]
- [[_COMMUNITY_URL Utilities|URL Utilities]]
- [[_COMMUNITY_Progress Dashboard|Progress Dashboard]]
- [[_COMMUNITY_XRegExpPrettify Bundle|XRegExp/Prettify Bundle]]
- [[_COMMUNITY_MB Details (Measurement Book)|MB Details (Measurement Book)]]
- [[_COMMUNITY_Python Dependencies|Python Dependencies]]
- [[_COMMUNITY_ExcelSheet Upload Pipeline|Excel/Sheet Upload Pipeline]]
- [[_COMMUNITY_App Config Layer|App Config Layer]]
- [[_COMMUNITY_Frontend Static Assets|Frontend Static Assets]]
- [[_COMMUNITY_Select2 Widget|Select2 Widget]]
- [[_COMMUNITY_Work Item Parser|Work Item Parser]]
- [[_COMMUNITY_PDF Parser|PDF Parser]]
- [[_COMMUNITY_Django Admin Actions|Django Admin Actions]]
- [[_COMMUNITY_Work Details API|Work Details API]]
- [[_COMMUNITY_Database Migrations|Database Migrations]]
- [[_COMMUNITY_Document Generator API|Document Generator API]]
- [[_COMMUNITY_Theme Toggle|Theme Toggle]]
- [[_COMMUNITY_Django Management Entry|Django Management Entry]]
- [[_COMMUNITY_Extension Bill Migration|Extension Bill Migration]]
- [[_COMMUNITY_Supply Quantity Migration|Supply Quantity Migration]]
- [[_COMMUNITY_Consignee Migration|Consignee Migration]]
- [[_COMMUNITY_UserProfile Migration|UserProfile Migration]]
- [[_COMMUNITY_Entry Type Migration|Entry Type Migration]]
- [[_COMMUNITY_Inspection Date Migration|Inspection Date Migration]]
- [[_COMMUNITY_WorkItemEntry Migration|WorkItemEntry Migration]]
- [[_COMMUNITY_Drop WorkBill Migration|Drop WorkBill Migration]]
- [[_COMMUNITY_MB Record Migration|MB Record Migration]]
- [[_COMMUNITY_WSGI Config|WSGI Config]]
- [[_COMMUNITY_ASGI Config|ASGI Config]]
- [[_COMMUNITY_Django Settings|Django Settings]]
- [[_COMMUNITY_Name of Work Migration|Name of Work Migration]]
- [[_COMMUNITY_Receive Note Migration|Receive Note Migration]]
- [[_COMMUNITY_Measurement Date Migration|Measurement Date Migration]]
- [[_COMMUNITY_Project CLAUDE Instructions|Project CLAUDE Instructions]]

## God Nodes (most connected - your core abstractions)
1. `Work` - 60 edges
2. `WorkItem` - 60 edges
3. `MBItem` - 33 edges
4. `MBRecord` - 31 edges
5. `WorkItemEntry` - 27 edges
6. `MBRecordSerializer` - 26 edges
7. `ManageWorks Backend` - 25 edges
8. `WorkExtension` - 24 edges
9. `WorkItemEntrySerializer` - 21 edges
10. `WorkEditSerializer` - 19 edges

## Surprising Connections (you probably didn't know these)
- `Vue 3 + Vite Frontend` --semantically_similar_to--> `LOA 38264 Marvel Telecom Progress Dashboard`  [INFERRED] [semantically similar]
  frontend/README.md → fff/README.md
- `clean_str()` --calls--> `parse_and_save_work_excel()`  [INFERRED]
  fff/build_data.py → backend/add_work/services/excel_parser.py
- `o()` --calls--> `G()`  [INFERRED]
  backend/staticfiles/admin/js/vendor/select2/select2.full.min.js → backend/staticfiles/rest_framework/js/jquery-3.7.1.min.js
- `WorkSearchView` --uses--> `Work`  [INFERRED]
  backend/work_details/views.py → backend/works/models.py
- `WorkSearchView` --uses--> `WorkSerializer`  [INFERRED]
  backend/work_details/views.py → backend/works/serializers.py

## Hyperedges (group relationships)
- **Marvel LOA 38264 Dashboard Data Pipeline** — fff_readme_source_xlsx, fff_readme_build_data_py, fff_readme_data_json, fff_readme_dashboard_html [EXTRACTED 0.95]
- **KPI Financial Metrics Cluster** — fff_readme_kpi_strip, fff_readme_weighted_progress, fff_readme_rebate_rate, fff_readme_baseline_reconciliation [INFERRED 0.85]
- **Schedule A and B Progress Split** — fff_readme_schedule_a, fff_readme_schedule_b, fff_readme_material_supply_progress, fff_readme_execution_progress [EXTRACTED 0.95]

## Communities

### Community 0 - "Django REST API Layer"
Cohesion: 0.07
Nodes (71): APIView, DashboardStatsView, ProgressTrendView, GET /api/dashboard/trend/?period=daily|weekly|monthly|yearly&loa_id=<id>     Onl, ItemSearchView, GET /api/item-progress/search/?q=cable&work_ids=1,2,3     Returns WorkItems matc, GET /api/item-progress/works/ — lightweight work list for the dropdown., WorkListView (+63 more)

### Community 1 - "jQuery Core Library"
Cohesion: 0.04
Nodes (55): addCombinator(), adoptValue(), ajaxConvert(), ajaxHandleResponses(), Animation(), assert(), boxModelAdjustment(), buildFragment() (+47 more)

### Community 2 - "Django Admin Popups"
Cohesion: 0.03
Nodes (27): addPopupIndex(), dismissAddRelatedObjectPopup(), dismissChangeRelatedObjectPopup(), dismissDeleteRelatedObjectPopup(), dismissRelatedLookupPopup(), removePopupIndex(), showAdminPopup(), showRelatedObjectLookupPopup() (+19 more)

### Community 3 - "Bootstrap/jQuery Bundle"
Cohesion: 0.07
Nodes (50): Ye(), e(), i(), l(), n(), r(), s(), u() (+42 more)

### Community 4 - "Django App Registry"
Cohesion: 0.06
Nodes (28): handleLogout(), authHeaders(), getCsrfToken(), login(), logout(), register(), UserProfileAdmin, UserProfile (+20 more)

### Community 5 - "jQuery Minified Build"
Cohesion: 0.09
Nodes (37): $(), A(), Ae(), B(), Be(), c(), $e(), ee() (+29 more)

### Community 6 - "URL Utilities"
Cohesion: 0.07
Nodes (27): downcode(), URLify(), _arrayLikeToArray(), augment(), buildAstral(), cacheAstral(), cacheInvertedBmp(), charCode() (+19 more)

### Community 7 - "Progress Dashboard"
Cohesion: 0.08
Nodes (37): Baseline Reconciliation (3 Source Metrics), build_data.py Data Pipeline Script, Cross-Filtering Interactivity, LOA 38264 Marvel Telecom Progress Dashboard, dashboard.html Self-Contained Dashboard File, Data Cleaning Rules (build_data.py), data.json Cleaned Data Payload, Dashboard Design Notes (Colours, Typography) (+29 more)

### Community 8 - "XRegExp/Prettify Bundle"
Cohesion: 0.09
Nodes (19): B(), C(), D(), E(), L(), M(), u(), x() (+11 more)

### Community 9 - "MB Details (Measurement Book)"
Cohesion: 0.13
Nodes (23): applyBulkPct(), closeEdit(), deleteRecord(), editRowAmount(), editRowIsValid(), fmtMbNum(), importPdf(), loadRecords() (+15 more)

### Community 10 - "Python Dependencies"
Cohesion: 0.13
Nodes (26): asgiref, certifi, cffi, charset-normalizer, cryptography, Django, django-cors-headers, djangorestframework (+18 more)

### Community 11 - "Excel/Sheet Upload Pipeline"
Cohesion: 0.11
Nodes (10): _download_google_sheet(), Extract the spreadsheet ID from a Google Sheets sharing URL., Download a publicly shared Google Sheet as xlsx using curl., _sheet_id_from_url(), UploadWorkView, clean_str(), Build the clean JSON payload for the Marvel LOA-38264 dashboard., Convert NaN/NaT/numpy scalars to JSON-safe natives. (+2 more)

### Community 12 - "App Config Layer"
Cohesion: 0.11
Nodes (10): AddWorkConfig, AppConfig, DashboardConfig, DocumentsConfig, ItemProgressConfig, MbDetailsConfig, UpdateWorkConfig, UsersConfig (+2 more)

### Community 13 - "Frontend Static Assets"
Cohesion: 0.17
Nodes (19): Bluesky Social Icon, Discord Icon, Documentation Icon, ManageWorks Favicon (Lightning Bolt Logo), Frontend Source Assets Directory, Frontend Public Assets Directory, GitHub Icon, Hero Image (Isometric Layered Shapes) (+11 more)

### Community 15 - "Select2 Widget"
Cohesion: 0.15
Nodes (8): b(), D(), e(), i(), o(), S(), u(), y()

### Community 16 - "Work Item Parser"
Cohesion: 0.22
Nodes (14): _extract_text(), _normalize_serial(), _normalize_unit(), _parse_header(), _parse_item_block(), parse_rm_pdf(), PDF parser for IRWCMS-format Record Measurement (RM) MBs.  Extracts: MB number,, Parse an IRWCMS Record Measurement PDF.      Returns dict:       {         'head (+6 more)

### Community 17 - "PDF Parser"
Cohesion: 0.22
Nodes (12): _clean_desc(), _clean_sno(), _lv_find(), _parse_date(), parse_receipt_pdf(), Strip trailing dashes, slashes, spaces from serial/item numbers., Strip surrounding quotes/smart-quotes and normalise whitespace., Extract label→value pairs from PDF tables (handles 2- and 4-column rows). (+4 more)

### Community 18 - "Django Admin Actions"
Cohesion: 0.38
Nodes (8): checker(), clearAcross(), hide(), reset(), show(), showClear(), showQuestion(), updateCounter()

### Community 19 - "Work Details API"
Cohesion: 0.47
Nodes (3): _base_queryset(), _items_queryset(), WorkSearchView

### Community 21 - "Database Migrations"
Cohesion: 0.5
Nodes (1): Migration

### Community 22 - "Document Generator API"
Cohesion: 0.5
Nodes (1): DocumentGeneratorView

### Community 23 - "Theme Toggle"
Cohesion: 0.83
Nodes (3): cycleTheme(), initTheme(), setTheme()

### Community 25 - "Django Management Entry"
Cohesion: 0.67
Nodes (2): main(), Run administrative tasks.

### Community 29 - "Extension Bill Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 30 - "Supply Quantity Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 31 - "Consignee Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 32 - "UserProfile Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 33 - "Entry Type Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 34 - "Inspection Date Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 35 - "WorkItemEntry Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 36 - "Drop WorkBill Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 37 - "MB Record Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 38 - "WSGI Config"
Cohesion: 1.0
Nodes (1): WSGI config for config project.  It exposes the WSGI callable as a module-level

### Community 39 - "ASGI Config"
Cohesion: 1.0
Nodes (1): ASGI config for config project.  It exposes the ASGI callable as a module-level

### Community 40 - "Django Settings"
Cohesion: 1.0
Nodes (1): Django settings for config project.  Generated by 'django-admin startproject' us

### Community 41 - "Name of Work Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 42 - "Receive Note Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 43 - "Measurement Date Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 81 - "Project CLAUDE Instructions"
Cohesion: 1.0
Nodes (1): ManageWorks CLAUDE.md

## Knowledge Gaps
- **46 isolated node(s):** `Build the clean JSON payload for the Marvel LOA-38264 dashboard.`, `Convert NaN/NaT/numpy scalars to JSON-safe natives.`, `Run administrative tasks.`, `Meta`, `A single lot submission for a WorkItem.     entry_type='supply'    → full inspec` (+41 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Database Migrations`** (4 nodes): `0001_initial.py`, `0001_initial.py`, `0001_initial.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Document Generator API`** (4 nodes): `urls.py`, `views.py`, `DocumentGeneratorView`, `.post()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Django Management Entry`** (3 nodes): `main()`, `manage.py`, `Run administrative tasks.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Extension Bill Migration`** (2 nodes): `0006_work_extension_bill.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Supply Quantity Migration`** (2 nodes): `0002_workitem_challan_no_workitem_supplied_quantity_and_more.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Consignee Migration`** (2 nodes): `0004_work_add_consignee.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `UserProfile Migration`** (2 nodes): `0003_workitem_updated_at_workitem_updated_by_userprofile.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Entry Type Migration`** (2 nodes): `0007_entry_type_location_remarks_executed_qty.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Inspection Date Migration`** (2 nodes): `0008_workitementry_date_of_inspection_and_more.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `WorkItemEntry Migration`** (2 nodes): `0005_workitementry.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Drop WorkBill Migration`** (2 nodes): `0009_drop_workbill.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `MB Record Migration`** (2 nodes): `0002_alter_mbrecord_mb_number.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `WSGI Config`** (2 nodes): `wsgi.py`, `WSGI config for config project.  It exposes the WSGI callable as a module-level`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `ASGI Config`** (2 nodes): `asgi.py`, `ASGI config for config project.  It exposes the ASGI callable as a module-level`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Django Settings`** (2 nodes): `settings.py`, `Django settings for config project.  Generated by 'django-admin startproject' us`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Name of Work Migration`** (2 nodes): `0010_add_name_of_work.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Receive Note Migration`** (2 nodes): `0011_workitementry_receive_note_date.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Measurement Date Migration`** (2 nodes): `0003_add_measurement_date.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Project CLAUDE Instructions`** (1 nodes): `ManageWorks CLAUDE.md`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Q()` connect `Bootstrap/jQuery Bundle` to `Django REST API Layer`, `Work Details API`?**
  _High betweenness centrality (0.194) - this node is a cross-community bridge._
- **Why does `$()` connect `Django Admin Popups` to `Bootstrap/jQuery Bundle`?**
  _High betweenness centrality (0.176) - this node is a cross-community bridge._
- **Why does `matcher()` connect `jQuery Core Library` to `Django Admin Popups`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Are the 58 inferred relationships involving `Work` (e.g. with `WorkSearchView` and `WorkAdmin`) actually correct?**
  _`Work` has 58 INFERRED edges - model-reasoned connections that need verification._
- **Are the 58 inferred relationships involving `WorkItem` (e.g. with `WorkSearchView` and `WorkAdmin`) actually correct?**
  _`WorkItem` has 58 INFERRED edges - model-reasoned connections that need verification._
- **Are the 28 inferred relationships involving `MBItem` (e.g. with `Work` and `WorkItem`) actually correct?**
  _`MBItem` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Are the 28 inferred relationships involving `MBRecord` (e.g. with `Work` and `WorkItem`) actually correct?**
  _`MBRecord` has 28 INFERRED edges - model-reasoned connections that need verification._