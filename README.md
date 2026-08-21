# AI Personal Lab Report Interpreter

A prototype that reads a patient's lab report, computes which results are high, low, or normal from reference ranges, and uses a language model to turn the flagged results into a plain language summary, lifestyle suggestions, and questions to bring to a doctor.

Built for MSBA 6461: Advanced AI for Natural Language Processing, Summer 2026.

## What this repo contains

- `1. Data Extraction/` — scripts that sample and clean the MIMIC-IV lab data and build the SQLite database the app reads from.
- `2. EDA/` — the exploratory analysis script and the charts it produces.
- `3. App/` — the Streamlit application: page code, the SQL layer, the report parsers, and the OpenAI integration.
- `4. Usage 3 Try Samples/` — fictional sample lab reports (not real patient data) used to test the upload feature.

## What this repo does not contain

The demo data comes from the MIMIC-IV Clinical Database, which requires completing PhysioNet's credentialing process and signing a data use agreement before access. That agreement does not allow redistributing the data, so this repo does not include the raw CSVs, the built `health_interpreter.db`, or the spreadsheet preview of it.

To run this locally with real data, get your own credentialed access to MIMIC-IV on PhysioNet, place the raw files under `0. Data Resources/`, then run the two scripts in `1. Data Extraction/` in order to rebuild the database.

## Running it locally

1. `cd "3. App"` and install the dependencies: `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and add your own OpenAI API key.
3. Build the database first (see above), or point `db.py` at your own copy of `health_interpreter.db`.
4. Run `streamlit run app.py`.

## How it works

Every result's status (high, low, normal) is computed in SQL from its reference range before anything reaches the language model. The model is only asked to explain results that have already been classified, never to decide the classification itself. A single OpenAI request per report returns a summary, lifestyle suggestions, and doctor questions together, and each finding is labeled with whether it came from the curated reference database or the model's general knowledge.
