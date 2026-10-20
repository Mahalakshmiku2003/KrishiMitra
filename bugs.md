# KrishiMitra - Comprehensive System Bug Report

This document outlines all identified architectural flaws, schema mismatches, runtime exceptions, dead code, and resolved fixes across the codebase.

---

## 1. Outbreak Notification System

### 1.1 Column Mismatch in Outbreak Target Farmers Query
- **Location**: `backend/outbreak/service.py` (`handle_new_detection`), `backend/outbreak/db_queries.py` (`get_all_farmers`)
- **Status**: [FIXED]
- **Details**: Updated `service.py` to safely access farmer crop lists using `(f.get("crops") or [])`, preventing unhandled `KeyError` when records lack explicit `crops` keys.

### 1.2 Deprecated / Invalid Groq Model in Outbreak AI Preventive Steps
- **Location**: `backend/outbreak/service.py`
- **Status**: [FIXED]
- **Details**: Replaced decommissioned `llama3-8b-8192` with `llama-3.3-70b-versatile`.

### 1.3 Outbreak Scheduled Task Uses Sync DB Session in Event Loop
- **Location**: `backend/outbreak/scheduler.py` (`check_new_detections`)
- **Status**: [FIXED]
- **Details**: Offloaded synchronous database queries (`_fetch_unprocessed_outbreaks`) and status update commits (`_mark_detection_processed`) to background worker threads using `asyncio.to_thread`, preventing event loop blocking during polling.

---

## 2. WhatsApp Webhook Consolidation

### 2.1 Conflicting WhatsApp Webhook Handlers
- **Location**: `backend/routes/whatsapp.py`, `backend/services/whatsapp_service.py`, `backend/agent/whatsapp.py`
- **Status**: [FIXED]
- **Details**:
  - Unified everything into `routes/whatsapp.py` and `services/whatsapp_service.py`, adhering to the standard modular layout.
  - Ported the structured farmer information extraction (`extract_farmer_data`) and automatic farmer profile updates (`location`, `crop`, `language`) from `agent/whatsapp.py` into `services/whatsapp_service.py` and `farmer_store.py`.
  - Added compatibility routes (`/webhook/whatsapp`, `/whatsapp`, and `/whatsapp/test`) to `routes/whatsapp.py`.
  - Removed redundant `backend/agent/whatsapp.py` and `backend/agent/main.py`.
  - Cleaned duplicate router inclusion in `backend/main.py`.

---

## 3. Database Fragmentation & Schema Inconsistencies

### 3.1 Multiple Incompatible Database Connections & Engines
- **Location**:
  - `backend/services/db.py`: Synchronous SQLAlchemy engine connecting via `DATABASE_URL` / `SUPABASE_DB_URL` with SSL support.
  - `backend/db/database.py`: Async SQLAlchemy engine (`postgresql+asyncpg://postgres:16122003@localhost:5432/krishimitra`) hardcoded with local credentials.
  - `backend/db/connection.py`: Standalone raw `psycopg2` connector with `RealDictCursor`.
- **Severity**: Critical. Hardcoded local credentials cause connection errors if `db/deps.py` is invoked in environments without local postgres.

### 3.2 Farmer Table Inconsistency: Relational vs. Raw JSON Columns
- **Location**: `backend/db/models.py` vs `backend/farmer_store.py`
  - In `backend/db/models.py`: Farmers have `phone_number`, `name`, `location`, `language`, and separate tables `FarmerCrop` and `FarmerDisease`.
  - In `backend/farmer_store.py`: Raw SQL assumes columns `phone`, `crops` (jsonb/array), `location`, `soil_type`, `history`, `messages`, `language`, `last_detection` (jsonb), `lat`, `lng`.
- **Severity**: High. Requires unification to avoid conflicting schemas across modules.

---

## 4. Model & Route Issues

### 4.1 Missing Dependencies in `requirements.txt`
- **Location**: `backend/requirements.txt`
- **Bug Description**:
  - `backend/services/yolo_service.py` imports `from ultralytics import YOLO`. However, `ultralytics`, `torch`, and `torchvision` were removed from `requirements.txt`.
- **Severity**: High. Endpoints importing `yolo_service` fail if YOLO is invoked without ultralytics installed.

### 4.2 Hardcoded / Obsolete Llama Vision Model in Soil Analysis Route
- **Location**: `backend/routes/soil.py` (line 86)
- **Bug Description**:
  `soil_deficiency` calls Groq with model: `meta-llama/llama-4-scout-17b-16e-instruct`. Groq does not support this model ID.
- **Severity**: High. Route `POST /soil/` fails with Groq ModelNotFoundError.

### 4.3 Route Prefix Doubling in `routes/market.py`
- **Location**: `backend/routes/market.py`
- **Status**: [FIXED]
- **Details**: Removed redundant `prefix="/market"` inside `routes/market.py` since `main.py` mounts it with `prefix="/market"`.

---

## 5. Dead Code & Unused Files Cleanup

### Cleaned Files:
1. `backend/database.py` - Removed (duplicate standalone database module).
2. `backend/data_access.py` - Removed (unused helper).
3. `backend/outbreak/utils.py` - Removed (empty 0-byte file).
4. `backend/services/alert_service.py` - Removed (superseded by `farmer_store.py`).
5. `backend/services/image_utils.py` - Removed (unreferenced compression script).
6. `backend/services/disease_search.py` - Removed (unintegrated embedding search).
7. `backend/tests/test_diagnose.py` - Removed (empty 0-byte file).
8. `documentation.txt` - Removed (empty 0-byte file).
9. `backend/agent/whatsapp.py` - Removed (features merged into `routes/whatsapp.py` & `services/whatsapp_service.py`).
10. `backend/agent/main.py` - Removed (redundant old app entry point).
