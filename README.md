# AI Personal Lab Report Interpreter

A prototype that reads a patient's lab report, computes which results are high, low, or normal from reference ranges, and uses a language model to turn the flagged results into a plain language summary, lifestyle suggestions, and questions to bring to a doctor.

Built for MSBA 6461, Advanced AI for Natural Language Processing, Summer 2026.

Try it live at https://ai-personal-lab-report-interpreter1.streamlit.app, no install needed.

## Using the app

The home page gives three ways to pick a report. Three Patients' Demo offers three curated synthetic patients, one all normal, one with a mild A1C, one with high lipids, as one click walkthroughs. Search Sample Database by id lets you search and filter the full 100 patient synthetic database by id, gender, age, panel, or lab pattern. Upload Your Report lets you drop your own report in PDF, PNG, JPG, JPEG, or CSV format, and it gets parsed the same way as the built in samples.

From there each report moves through three pages. Extracted Results shows every test, value, unit, and reference range, with a computed HIGH, LOW, or NORMAL status and where that status's range came from. AI Summary sends one OpenAI request that turns the flagged results into a plain language summary, and labels each finding as coming from the curated reference database or the model's general knowledge. Lifestyle and Doctor Questions gives lifestyle suggestions and questions to bring to a doctor, generated from that same request.

The AI Summary and Lifestyle and Doctor Questions pages need an OpenAI key, described below. Extracted Results does not.

## How status is computed

Every result's status is computed before anything reaches the language model, and the model never decides it. The reference range used is the one printed on the report itself when present. When a recognized test is missing its own range, the app falls back to a curated range cited to a public source such as MedlinePlus Medical Encyclopedia or Cleveland Clinic, listed in `app/utils/curated_ranges.py`.

## What this repo contains

`Data Extraction` holds the SQLite database the app reads from, `health_interpreter.db`, plus the scripts used to build a database from raw lab data. `EDA` holds the exploratory analysis script and the charts it produces. `app` holds the Streamlit application, the page code, the SQL layer, the report parsers, and the OpenAI integration. `Usage 3 Try Samples` holds fictional sample lab reports, not real patient data, used to test the upload feature.

## About the demo data

`Data Extraction/health_interpreter.db` is a hand built synthetic dataset, 100 fictional patients, 100 encounters, and 1,300 lab results. It is not derived from MIMIC IV or any PhysioNet credentialed source, which is why it's safe to ship in this public repo and deploy without a data use agreement. `subject_id` and `hadm_id` values intentionally use the 900xx and 901xx range so they're never confused with real MIMIC ids.

`Data Extraction/build_database.py` and `extract_labevents_sample.py` are the original scripts written against the real MIMIC IV Clinical Database during earlier coursework. They expect raw MIMIC CSVs, which require completing PhysioNet's credentialing process and are not included or redistributed here, and are kept only for reference. You don't need them to run the app against the synthetic database already in the repo.

## Running it locally

The live demo above needs nothing installed. To run your own copy instead, move into the `app` folder and install the dependencies with `pip install -r requirements.txt`. Copy `.env.example` to `.env` and add your own OpenAI API key. This is only needed for the AI Summary and Lifestyle and Doctor Questions pages, since Extracted Results doesn't require a key. Then run `streamlit run app.py`. It reads `Data Extraction/health_interpreter.db` by default, so point `db.py` at your own copy of the database if you want to use different data.
