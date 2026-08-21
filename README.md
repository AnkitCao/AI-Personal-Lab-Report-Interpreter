# AI Personal Lab Report Interpreter

A prototype that reads a patient's lab report, computes which results are high, low, or normal from reference ranges, and uses a language model to turn the flagged results into a plain language summary, lifestyle suggestions, and questions to bring to a doctor.

Built for MSBA 6461: Advanced AI for Natural Language Processing, Summer 2026.

Live demo: https://ai-personal-lab-report-interpreter1.streamlit.app

## What this repo contains

- `Data Extraction/` — the SQLite database the app reads from (`health_interpreter.db`), plus the scripts used to build a database from raw lab data.
- `EDA/` — the exploratory analysis script and the charts it produces.
- `app/` — the Streamlit application: page code, the SQL layer, the report parsers, and the OpenAI integration.
- `Usage 3 Try Samples/` — fictional sample lab reports (not real patient data) used to test the upload feature.

## About the demo data

`Data Extraction/health_interpreter.db` is a hand-built **synthetic** dataset — 100 fictional patients, 100 encounters, and 1,300 lab results. It is not derived from MIMIC-IV or any PhysioNet-credentialed source, which is why it's safe to ship in this public repo and deploy without a data use agreement. `subject_id` / `hadm_id` values intentionally use the 900xx / 901xx range so they're never confused with real MIMIC ids.

`Data Extraction/build_database.py` and `extract_labevents_sample.py` are the original scripts written against the real MIMIC-IV Clinical Database during earlier coursework. They expect raw MIMIC CSVs (which require completing PhysioNet's credentialing process and are not included or redistributed here) and are kept for reference — you don't need them to run the app against the synthetic database that's already in the repo.

## Running it locally

1. `cd app` and install the dependencies: `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and add your own OpenAI API key. This is only needed for the "Generate AI Summary" step — extracting and classifying results doesn't require a key.
3. Run `streamlit run app.py`. It reads `Data Extraction/health_interpreter.db` by default; point `db.py` at your own copy of the database if you want to use different data.

## How it works

Every result's status (high, low, normal) is computed from its reference range before anything reaches the language model — either the range printed on the report itself, or, when a recognized test's report doesn't include one, a curated fallback range cited to a public source (MedlinePlus Medical Encyclopedia, Cleveland Clinic, and similar) in `app/utils/curated_ranges.py`. The model is only asked to explain results that have already been classified, never to decide the classification itself. A single OpenAI request per report returns a summary, lifestyle suggestions, and doctor questions together, and each finding is labeled with whether it came from the curated reference database or the model's general knowledge.
