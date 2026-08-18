# TDS Project 2 analysis code

Reproducible, read-only analysis scripts for the Project 2 case studies. Source
data is intentionally excluded from the repository.

## Setup

```bash
python -m pip install -r requirements.txt
```

Run each script against a directory containing the question files:

```bash
python analysis/q1_month_end.py --data-dir /path/to/data
python analysis/q2_nova_ivr.py --data-dir /path/to/data
python analysis/q3_inverter_smell.py --data-dir /path/to/data
python analysis/q4_dsm_impact.py --data-dir /path/to/data
python analysis/q5_swiss_mismatch.py --data-dir /path/to/data
python analysis/q6_qc_queue.py --data-dir /path/to/data
python analysis/q7_irish_preference.py --data-dir /path/to/data
python analysis/q8_spares_search.py --data-dir /path/to/data
```

Each script prints compact JSON metrics so every statement used in a diagnostic
note can be traced back to the supplied files.
