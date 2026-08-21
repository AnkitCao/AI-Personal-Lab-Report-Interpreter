# AI Personal Lab Report Interpreter

A tool that reads a patient's lab report, computes which results are high, low, or normal against reference ranges, and uses a language model to turn the flagged results into a plain language summary, lifestyle suggestions, and questions to bring to a doctor.

Try it live at https://ai-personal-lab-report-interpreter1.streamlit.app, no install needed.

## Using the app

Start on the home page. It offers three ways to load a report.

1. **Three Patients' Demo.** Three curated synthetic patients, one all normal, one with a mild A1C, one with high lipids, set up as one click walkthroughs.
2. **Search Sample Database by id.** Search and filter the full 100 patient synthetic database by id, gender, age, panel, or lab pattern.
3. **Upload Your Report.** Drop your own report in PDF, PNG, JPG, JPEG, or CSV format. It gets parsed the same way as the built in samples.

Once a report is loaded, it moves through three pages.

1. **Extracted Results.** Every test, value, unit, and reference range, with a computed HIGH, LOW, or NORMAL status and where that status's range came from.
2. **AI Summary.** One OpenAI request turns the flagged results into a plain language summary. Each finding is labeled as coming from the curated reference database or the model's general knowledge.
3. **Lifestyle and Doctor Questions.** Lifestyle suggestions and questions to bring to a doctor, generated from that same request.

AI Summary and Lifestyle and Doctor Questions need an OpenAI key. Extracted Results does not.

## How status is computed

Status is HIGH, LOW, or NORMAL, showing whether a result falls above, below, or inside its reference range. Every result's status is computed before anything reaches the language model, and the model never decides it. The reference range used is the one printed on the report itself when present. When a recognized test is missing its own range, the app falls back to a curated range cited to a public source, listed in `app/utils/curated_ranges.py`.

| Source | Tests covered |
| --- | --- |
| MedlinePlus Medical Encyclopedia, Comprehensive metabolic panel | Glucose, Sodium, Potassium, Urea Nitrogen, Creatinine, Total Calcium, Albumin, Total Bilirubin |
| Cleveland Clinic, Complete Blood Count | Hematocrit, Hemoglobin, Red Blood Cells, White Blood Cells, Platelet Count |
| MedlinePlus, Cholesterol Levels | Triglycerides, Total Cholesterol, LDL Cholesterol Calculated, LDL Cholesterol Measured |
| MedlinePlus Medical Encyclopedia, A1C test | Hemoglobin A1c |
| Healthline, Medical News Today, UMass Memorial Health library | Cholesterol Ratio |
| MIMIC IV, matched from non blank HDL rows in this sample | HDL Cholesterol |

## What this repo contains

- `Data Extraction`. The SQLite database the app reads from, `health_interpreter.db`, plus the scripts used to build a database from raw lab data.
- `EDA`. The exploratory analysis script and the charts it produces.
- `app`. The Streamlit application, the page code, the SQL layer, the report parsers, and the OpenAI integration.
- `Usage 3 Try Samples`. Fictional sample lab reports, not real patient data, used to test the upload feature.

## About the demo data

`Data Extraction/health_interpreter.db` is a hand built synthetic dataset, 100 fictional patients, 100 encounters, and 1,300 lab results. It is not derived from MIMIC IV or any PhysioNet credentialed source, which is why it's safe to ship in this public repo and deploy without a data use agreement. `subject_id` and `hadm_id` values intentionally use the 900xx and 901xx range so they're never confused with real MIMIC ids.

`Data Extraction/build_database.py` and `extract_labevents_sample.py` are the original pipeline scripts, written against the real MIMIC IV Clinical Database. They expect raw MIMIC CSVs, which require completing PhysioNet's credentialing process and are not included or redistributed here, and are kept only for reference. You don't need them to run the app against the synthetic database already in the repo.
