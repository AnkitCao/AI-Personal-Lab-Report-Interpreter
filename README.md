# AI Personal Lab Report Interpreter

A prototype that reads a patient's lab report, computes which results are high, low, or normal from reference ranges, and uses a language model to turn the flagged results into a plain language summary, lifestyle suggestions, and questions to bring to a doctor.

Built for MSBA 6461: Advanced AI for Natural Language Processing, Summer 2026.

**Try it live — no install needed: https://ai-personal-lab-report-interpreter1.streamlit.app**

## Using the app

The home page gives three ways to pick a report:

- **Three Patients' Demo** — three curated synthetic patients (all-normal, mild A1C, high lipids) as one-click walkthroughs.
- **Search Sample Database by id** — search and filter the full 100-patient synthetic database by id, gender, age, panel, or lab pattern.
- **Upload Your Report** — drop your own report (PDF, PNG, JPG/JPEG, or CSV) and it's parsed the same way.

From there each report flows through three pages:

1. **Extracted Results** — every test, value, unit, and reference range, with a computed HIGH / LOW / NORMAL status and where that status's range came from.
2. **AI Summary** — one OpenAI request turns the flagged results into a plain-language summary, with each finding labeled as coming from the curated reference database or the model's general knowledge.
3. **Lifestyle & Doctor Questions** — lifestyle suggestions and questions to bring to a doctor, generated from the same request.

The AI pages need an OpenAI key (see below); Extracted Results does not.

## How status is computed

Every result's status is computed before anything reaches the language model, never decided by it. The reference range used is, in order:

1. The range printed on the report itself, if present.
2. For a recognized test missing its own range, a curated fallback range cited to a public source (MedlinePlus Medical Encyclopedia, Cleveland Clinic, and similar) in `app/utils/curated_ranges.py`.

## What this repo contains

- `Data Extraction/` — the SQLite database the app reads from (`health_interpreter.db`), plus the scripts used to build a database from raw lab data.
- `EDA/` — the exploratory analysis script and the charts it produces.
- `app/` — the Streamlit application: page code, the SQL layer, the report parsers, and the OpenAI integration.
- `Usage 3 Try Samples/` — fictional sample lab reports (not real patient data) used to test the upload feature.

## About the demo data

`Data Extraction/health_interpreter.db` is a hand-built **synthetic** dataset — 100 fictional patients, 100 encounters, and 1,300 lab results. It is not derived from MIMIC-IV or any PhysioNet-credentialed source, which is why it's safe to ship in this public repo and deploy without a data use agreement. `subject_id` / `hadm_id` values intentionally use the 900xx / 901xx range so they're never confused with real MIMIC ids.

`Data Extraction/build_database.py` and `extract_labevents_sample.py` are the original scripts written against the real MIMIC-IV Clinical Database during earlier coursework. They expect raw MIMIC CSVs (which require completing PhysioNet's credentialing process and are not included or redistributed here) and are kept for reference — you don't need them to run the app against the synthetic database that's already in the repo.

## Running it locally

The live demo above needs nothing installed. To run your own copy instead:

1. `cd app` and install the dependencies: `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and add your own OpenAI API key. This is only needed for the AI Summary / Lifestyle & Doctor Questions pages — Extracted Results doesn't require a key.
3. Run `streamlit run app.py`. It reads `Data Extraction/health_interpreter.db` by default; point `db.py` at your own copy of the database if you want to use different data.
