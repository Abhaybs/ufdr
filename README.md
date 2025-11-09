# UFDR Forensic Analysis Toolkit

This project implements a three-phase roadmap for building a streamlined UFDR (Universal Forensic Data Report) web application. The initial focus (Phase 1) covers uploading a UFDR archive, parsing core data sources, storing normalized datasets, and presenting the results via a lightweight frontend.

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

3. **Run the FastAPI server**:

   ```bash
   uvicorn app.main:app --reload --app-dir backend
   ```

   The API will be available at `http://localhost:8000`.

4. _(Optional for later phases)_ Install additional dependencies:

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

5. **Serve the frontend** (simple option):

   ```bash
   python -m http.server 3000 --directory frontend
   ```

   Then open `http://localhost:3000` in your browser. The UI expects the API at `http://localhost:8000`.

   - Visit `http://localhost:3000/graph.html` for the Phase 2 knowledge-graph explorer (requires Neo4j).

6. **Need sample data?** Generate a synthetic UFDR archive:

   ```bash
   python backend/scripts/create_sample_ufdr.py
   ```

   This produces `storage/sample_data/sample.ufdr`, which you can upload through the UI.

## Current Capabilities (Phase 1)

## Phase 2 Smoke-Test Checklist

- Regenerate or upload a UFDR archive (e.g. `python backend/scripts/create_sample_ufdr.py`).
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

- Capture screenshots/logs of the ingestion summary, data tables, and graph explorer for documentation.
- Automate Gemini image descriptions and merge them into the search index.
- Harden parsers for additional UFDR data formats and device-specific schemas.
