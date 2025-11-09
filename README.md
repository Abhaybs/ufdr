# UFDR Forensic Analysis Toolkit

This project implements a three-phase roadmap for building a streamlined UFDR (Universal Forensic Data Report) web application. Phase 1 covers ingesting UFDR archives and rendering core tables. Phase 2 layers on Neo4j graph exploration. Phase 3 adds semantic search with Gemini text and vision models.

## Project Structure

```
backend/     FastAPI application, ingestion pipeline, and database layer
frontend/    Static HTML/CSS/JS assets for interacting with the API
storage/     Working directory for uploaded archives, extracted files, and SQLite database
```

## Getting Started

1. **Create a Python virtual environment** (Python 3.11 recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

2. **Install backend dependencies (Phase 1)**:

   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Provision environment variables**

Copy `.env.example` if present or set the following values in `.env`.

```ini
# Core storage and database settings (defaults are usually fine)
STORAGE_DIR=storage

# Gemini API (Phase 3)
GEMINI_API_KEY=your_api_key
GEMINI_MODEL_NAME=models/gemini-2.5-flash
GEMINI_VISION_MODEL_NAME=models/gemini-2.5-flash-image

# Neo4j (Phase 2) — leave NEO4J_ENABLED=false unless you have a live instance
NEO4J_ENABLED=false
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j
NEO4J_DATABASE=ufdr
```

Enable Gemini access in Google Cloud (Generative Language API) before running Phase 3 features.

4. **Run the FastAPI server**:

   ```bash
   uvicorn app.main:app --reload --app-dir backend
   ```

   The API will be available at `http://localhost:8000`.

5. _(Optional for later phases)_ Install additional dependencies:

   - **Phase 2 (Neo4j integration)**

     ```bash
     pip install -r backend/requirements-phase2.txt
     ```

     Configure `.env` (or environment variables) so the backend knows how to reach your Neo4j instance:

     ```ini
     NEO4J_ENABLED=true
     NEO4J_URI=bolt://localhost:7687
     NEO4J_USER=neo4j
     NEO4J_PASSWORD=your_password
     NEO4J_DATABASE=neo4j
     ```

     Start Neo4j Desktop or your preferred Neo4j server before running the ingestion pipeline.

   - **Phase 3 (Vector search & Gemini)**

     ```bash
     pip install -r backend/requirements-phase3.txt
     ```

     > `chromadb` pulls in `chroma-hnswlib`, which requires Microsoft C++ Build Tools on Windows. Install the Build Tools from the [official download page](https://visualstudio.microsoft.com/visual-cpp-build-tools/) before running the Phase 3 install.

6. **Serve the frontend** (simple option):

   ```bash
   python -m http.server 3000 --directory frontend
   ```

   Then open `http://localhost:3000` in your browser. The UI expects the API at `http://localhost:8000`.

   - Visit `http://localhost:3000/graph.html` for the Phase 2 knowledge-graph explorer (requires Neo4j).

7. **Need sample data?** Generate a synthetic UFDR archive:

   ```bash
   python backend/scripts/create_sample_ufdr.py storage/sample_data/sample.ufdr
   ```

   - Add real imagery for Gemini Vision:

     ```bash
     python backend/scripts/create_sample_ufdr.py \
       storage/sample_data/sample.ufdr \
       --red-image "C:/path/to/photo-one.jpg" \
       --blue-image "C:/path/to/photo-two.jpg"
     ```

   The script copies your media into `media/images/` inside the archive so Gemini can produce captions.

8. **Ingest an archive**

   - Upload in the UI (Data Tables → Upload) or call the API:

     ```bash
     curl -X POST http://127.0.0.1:8000/api/ingest/ufdr \
       -H "Content-Type: multipart/form-data" \
       -F "file=@storage/sample_data/sample.ufdr"
     ```

   - Watch the `uvicorn` console for Gemini caption logs. Successful rows appear in `storage/main.db` → `images` with `caption_status="done"`.

9. **Ask questions with the assistant** (Phase 3)

   ```bash
   curl -X POST http://127.0.0.1:8000/api/query \
     -H "Content-Type: application/json" \
     -d '{"question":"Show me the red car photo"}'
   ```

   - The response `answer` references the relevant records and includes an evidence list.
   - Set `include_images=true` in the payload if you need base64 thumbnails.

10. **Inspect stored data**

    ```bash
    python - <<'PY'
    import sqlite3
    from pathlib import Path
    conn = sqlite3.connect(Path("storage/main.db"))
    cur = conn.cursor()
    print(cur.execute("SELECT id, relative_path, description, tags, caption_status FROM images").fetchall())
    conn.close()
    PY
    ```

    - Delete old runs by removing `storage/main.db` and `storage/vector_store` before re-ingesting.
    - The ingestion API always appends; clear tables if starting from zero.

## Phase 2: Neo4j Graph Explorer

- Regenerate or upload a UFDR archive (e.g. `python backend/scripts/create_sample_ufdr.py`).
- Ensure Neo4j is running. Easiest local setup:
  - Docker: `docker run --rm -it -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/12345678 neo4j:5.22`.
  - In the Neo4j browser execute `CREATE DATABASE ufdr IF NOT EXISTS;` and switch the primary database if required.
- Set `NEO4J_ENABLED=true` in `.env` and restart `uvicorn`.
- Start services:
  - `uvicorn app.main:app --reload --app-dir backend`
  - `python -m http.server 3000 --directory frontend`
- Visit `http://localhost:3000` to confirm tables render. Open `graph.html`, search a contact, and ensure nodes/edges appear.
- Inspect `storage/main.db` if validation is needed (SQLite browser or shell).
- Run Neo4j maintenance helpers when repeating tests:

  - Reset graph via API:

    ```bash
    curl -X POST http://localhost:8000/api/graph/reset
    ```

  - Resync from SQLite (optionally clearing first):

    ```bash
    curl -X POST "http://localhost:8000/api/graph/resync?clear_first=true"
    ```

  - Or use the CLI wrapper:

    ```bash
    python backend/scripts/graph_admin.py resync --clear-first
    ```

## Troubleshooting

- **Gemini Vision returns `Unable to process input image`**: ensure images are >256×256 and visually meaningful. Replace synthetic 1×1 assets with real photos using the UFDR generator flags.
- **Gemini errors `404 models/... not found`**: check `GEMINI_MODEL_NAME` and `GEMINI_VISION_MODEL_NAME` in `.env`. Use models available to your API key (`models/gemini-2.5-flash`, `models/gemini-2.5-flash-image` confirmed).
- **Gemini quota exceeded**: upgrade your Google Cloud plan or wait for limits to reset; ingestion stores `caption_status` and `caption_error` for auditing.
- **Neo4j connection refused**: set `NEO4J_ENABLED=false` if you do not have an instance running. When enabled, confirm port 7687 is accessible and credentials match `.env`.
- **Frontend shows cached data**: hard refresh (`Ctrl+Shift+R`), or append `?v=2` to script URLs while developing.
