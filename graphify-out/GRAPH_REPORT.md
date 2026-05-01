# Graph Report - .  (2026-04-30)

## Corpus Check
- 1 files · ~5,000 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 330 nodes · 575 edges · 28 communities detected
- Extraction: 62% EXTRACTED · 38% INFERRED · 0% AMBIGUOUS · INFERRED: 221 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Django API Layer|Django API Layer]]
- [[_COMMUNITY_MB Records Module|MB Records Module]]
- [[_COMMUNITY_Dashboard & Analytics|Dashboard & Analytics]]
- [[_COMMUNITY_MB Details Vue UI|MB Details Vue UI]]
- [[_COMMUNITY_Django App Configs|Django App Configs]]
- [[_COMMUNITY_Frontend Static Assets|Frontend Static Assets]]
- [[_COMMUNITY_PDF Parser|PDF Parser]]
- [[_COMMUNITY_Data Build Pipeline|Data Build Pipeline]]
- [[_COMMUNITY_User Auth API|User Auth API]]
- [[_COMMUNITY_Work Upload & Excel|Work Upload & Excel]]
- [[_COMMUNITY_Vue App Bootstrap|Vue App Bootstrap]]
- [[_COMMUNITY_Work Search API|Work Search API]]
- [[_COMMUNITY_Document Generator|Document Generator]]
- [[_COMMUNITY_Django Entry Point|Django Entry Point]]
- [[_COMMUNITY_DB Migrations (Init)|DB Migrations (Init)]]
- [[_COMMUNITY_Extension Bill Migration|Extension Bill Migration]]
- [[_COMMUNITY_WorkItem Challan Migration|WorkItem Challan Migration]]
- [[_COMMUNITY_Consignee Migration|Consignee Migration]]
- [[_COMMUNITY_WorkItem Audit Migration|WorkItem Audit Migration]]
- [[_COMMUNITY_Item Entry Migration|Item Entry Migration]]
- [[_COMMUNITY_Inspection Date Migration|Inspection Date Migration]]
- [[_COMMUNITY_WorkItemEntry Migration|WorkItemEntry Migration]]
- [[_COMMUNITY_Drop WorkBill Migration|Drop WorkBill Migration]]
- [[_COMMUNITY_MB Number Migration|MB Number Migration]]
- [[_COMMUNITY_WSGI Config|WSGI Config]]
- [[_COMMUNITY_ASGI Config|ASGI Config]]
- [[_COMMUNITY_Django Settings|Django Settings]]
- [[_COMMUNITY_Claude Instructions|Claude Instructions]]

## God Nodes (most connected - your core abstractions)
1. `Work` - 46 edges
2. `WorkItem` - 45 edges
3. `MBItem` - 26 edges
4. `MBRecord` - 22 edges
5. `WorkItemEntry` - 20 edges
6. `MBRecordSerializer` - 20 edges
7. `WorkExtension` - 17 edges
8. `WorkItemEntrySerializer` - 15 edges
9. `WorkEditSerializer` - 13 edges
10. `LOA 38264 Marvel Telecom Progress Dashboard` - 13 edges

## Surprising Connections (you probably didn't know these)
- `Vue 3 + Vite Frontend` --semantically_similar_to--> `LOA 38264 Marvel Telecom Progress Dashboard`  [INFERRED] [semantically similar]
  frontend/README.md → fff/README.md
- `WorkSearchView` --uses--> `Work`  [INFERRED]
  backend/work_details/views.py → backend/works/models.py
- `WorkSearchView` --uses--> `WorkSerializer`  [INFERRED]
  backend/work_details/views.py → backend/works/serializers.py
- `Work` --uses--> `WorkSearchView`  [INFERRED]
  backend/works/models.py → backend/mb_details/views.py
- `Work` --uses--> `WorkItemSearchView`  [INFERRED]
  backend/works/models.py → backend/mb_details/views.py

## Communities

### Community 0 - "Django API Layer"
Cohesion: 0.1
Nodes (37): DashboardStatsView, ProgressTrendView, GET /api/dashboard/trend/?period=daily|weekly|monthly|yearly&loa_id=<id>     Onl, ItemSearchView, GET /api/item-progress/search/?q=cable&work_ids=1,2,3     Returns WorkItems matc, GET /api/item-progress/works/ — lightweight work list for the dropdown., WorkListView, Meta (+29 more)

### Community 1 - "MB Records Module"
Cohesion: 0.15
Nodes (23): APIView, MBItem, MBRecord, MBItemSerializer, MBRecordSerializer, Meta, _check_not_observer(), create() (+15 more)

### Community 2 - "Dashboard & Analytics"
Cohesion: 0.1
Nodes (32): Baseline Reconciliation (3 Source Metrics), build_data.py Data Pipeline Script, Cross-Filtering Interactivity, LOA 38264 Marvel Telecom Progress Dashboard, dashboard.html Self-Contained Dashboard File, Data Cleaning Rules (build_data.py), data.json Cleaned Data Payload, Dashboard Design Notes (Colours, Typography) (+24 more)

### Community 3 - "MB Details Vue UI"
Cohesion: 0.12
Nodes (16): applyBulkPct(), deleteRecord(), importPdf(), loadRecords(), loadSummary(), onPdfSelected(), pickWork(), resetFlow() (+8 more)

### Community 4 - "Django App Configs"
Cohesion: 0.11
Nodes (10): AddWorkConfig, AppConfig, DashboardConfig, DocumentsConfig, ItemProgressConfig, MbDetailsConfig, UpdateWorkConfig, UsersConfig (+2 more)

### Community 5 - "Frontend Static Assets"
Cohesion: 0.17
Nodes (19): Bluesky Social Icon, Discord Icon, Documentation Icon, ManageWorks Favicon (Lightning Bolt Logo), Frontend Source Assets Directory, Frontend Public Assets Directory, GitHub Icon, Hero Image (Isometric Layered Shapes) (+11 more)

### Community 6 - "PDF Parser"
Cohesion: 0.22
Nodes (14): _extract_text(), _normalize_serial(), _normalize_unit(), _parse_header(), _parse_item_block(), parse_rm_pdf(), PDF parser for IRWCMS-format Record Measurement (RM) MBs.  Extracts: MB number,, Parse an IRWCMS Record Measurement PDF.      Returns dict:       {         'head (+6 more)

### Community 8 - "Data Build Pipeline"
Cohesion: 0.2
Nodes (3): Build the clean JSON payload for the Marvel LOA-38264 dashboard., Convert NaN/NaT/numpy scalars to JSON-safe natives., to_native()

### Community 9 - "User Auth API"
Cohesion: 0.22
Nodes (4): MeView, GET /api/users/me/ — return the currently authenticated user., UserCreateView, UserListView

### Community 10 - "Work Upload & Excel"
Cohesion: 0.28
Nodes (4): Extract the spreadsheet ID from a Google Sheets sharing URL., _sheet_id_from_url(), UploadWorkView, parse_and_save_work_excel()

### Community 11 - "Vue App Bootstrap"
Cohesion: 0.5
Nodes (5): Vue 3 Script Setup SFCs, Vue 3 + Vite Frontend, Vue App Mount Point (#app), Frontend Entry Point (index.html), Main JS Entry (src/main.js)

### Community 12 - "Work Search API"
Cohesion: 0.5
Nodes (1): WorkSearchView

### Community 13 - "Document Generator"
Cohesion: 0.5
Nodes (1): DocumentGeneratorView

### Community 15 - "Django Entry Point"
Cohesion: 0.67
Nodes (2): main(), Run administrative tasks.

### Community 16 - "DB Migrations (Init)"
Cohesion: 0.67
Nodes (1): Migration

### Community 18 - "Extension Bill Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 19 - "WorkItem Challan Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 20 - "Consignee Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 21 - "WorkItem Audit Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 22 - "Item Entry Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 23 - "Inspection Date Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 24 - "WorkItemEntry Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 25 - "Drop WorkBill Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 26 - "MB Number Migration"
Cohesion: 1.0
Nodes (1): Migration

### Community 27 - "WSGI Config"
Cohesion: 1.0
Nodes (1): WSGI config for config project.  It exposes the WSGI callable as a module-level

### Community 28 - "ASGI Config"
Cohesion: 1.0
Nodes (1): ASGI config for config project.  It exposes the ASGI callable as a module-level

### Community 29 - "Django Settings"
Cohesion: 1.0
Nodes (1): Django settings for config project.  Generated by 'django-admin startproject' us

### Community 56 - "Claude Instructions"
Cohesion: 1.0
Nodes (1): ManageWorks CLAUDE.md

## Knowledge Gaps
- **32 isolated node(s):** `Build the clean JSON payload for the Marvel LOA-38264 dashboard.`, `Convert NaN/NaT/numpy scalars to JSON-safe natives.`, `Run administrative tasks.`, `Meta`, `A single lot submission for a WorkItem.     entry_type='supply'    → full inspec` (+27 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Work Search API`** (4 nodes): `urls.py`, `views.py`, `WorkSearchView`, `.get_queryset()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Document Generator`** (4 nodes): `urls.py`, `views.py`, `DocumentGeneratorView`, `.post()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Django Entry Point`** (3 nodes): `main()`, `manage.py`, `Run administrative tasks.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `DB Migrations (Init)`** (3 nodes): `0001_initial.py`, `0001_initial.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Extension Bill Migration`** (2 nodes): `0006_work_extension_bill.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `WorkItem Challan Migration`** (2 nodes): `0002_workitem_challan_no_workitem_supplied_quantity_and_more.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Consignee Migration`** (2 nodes): `0004_work_add_consignee.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `WorkItem Audit Migration`** (2 nodes): `0003_workitem_updated_at_workitem_updated_by_userprofile.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Item Entry Migration`** (2 nodes): `0007_entry_type_location_remarks_executed_qty.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Inspection Date Migration`** (2 nodes): `0008_workitementry_date_of_inspection_and_more.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `WorkItemEntry Migration`** (2 nodes): `0005_workitementry.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Drop WorkBill Migration`** (2 nodes): `0009_drop_workbill.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `MB Number Migration`** (2 nodes): `0002_alter_mbrecord_mb_number.py`, `Migration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `WSGI Config`** (2 nodes): `wsgi.py`, `WSGI config for config project.  It exposes the WSGI callable as a module-level`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `ASGI Config`** (2 nodes): `asgi.py`, `ASGI config for config project.  It exposes the ASGI callable as a module-level`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Django Settings`** (2 nodes): `settings.py`, `Django settings for config project.  Generated by 'django-admin startproject' us`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Claude Instructions`** (1 nodes): `ManageWorks CLAUDE.md`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Work` connect `Django API Layer` to `MB Records Module`, `Work Search API`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Why does `WorkItem` connect `Django API Layer` to `MB Records Module`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Why does `UploadWorkView` connect `Work Upload & Excel` to `MB Records Module`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Are the 44 inferred relationships involving `Work` (e.g. with `WorkSearchView` and `WorkAdmin`) actually correct?**
  _`Work` has 44 INFERRED edges - model-reasoned connections that need verification._
- **Are the 43 inferred relationships involving `WorkItem` (e.g. with `WorkAdmin` and `WorkItemAdmin`) actually correct?**
  _`WorkItem` has 43 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `MBItem` (e.g. with `Work` and `WorkItem`) actually correct?**
  _`MBItem` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `MBRecord` (e.g. with `Work` and `WorkItem`) actually correct?**
  _`MBRecord` has 19 INFERRED edges - model-reasoned connections that need verification._