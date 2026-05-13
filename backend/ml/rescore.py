"""
rescore.py — Re-score all existing candidates with the current model.
Usage: docker compose exec backend python /app/ml/rescore.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from src.config import settings
from src.models.cv_schema import CVSchema
from src.services.features import extract_features
from src.services.predictor import predict, _load_model

_load_model()

conn = psycopg2.connect(settings.database_url)
cur = conn.cursor()
cur.execute("SELECT id, cv_data FROM candidates WHERE cv_data IS NOT NULL ORDER BY id")
rows = cur.fetchall()
print(f"Re-scoring {len(rows)} candidates...")

updated = 0
errors = 0
for cand_id, cv_data_raw in rows:
    try:
        raw = cv_data_raw if isinstance(cv_data_raw, dict) else json.loads(cv_data_raw)
        cv = CVSchema(**raw)
        features = extract_features(cv)
        rec, conf, explanation = predict(features)
        cur.execute(
            "UPDATE candidates SET recommendation=%s, confidence=%s, explanation=%s WHERE id=%s",
            (rec, conf, json.dumps(explanation) if explanation else None, cand_id),
        )
        updated += 1
    except Exception as e:
        print(f"  Error {str(cand_id)[:8]}: {e}")
        errors += 1

conn.commit()
print(f"Committed — updated: {updated}, errors: {errors}")

cur.execute("SELECT recommendation, confidence FROM candidates ORDER BY confidence DESC")
rows = cur.fetchall()
cur.close()
conn.close()

print(f"\n{'Rec':<8} {'Conf':>8}")
for rec, conf in rows:
    bar = "█" * int((conf or 0) * 20)
    print(f"{rec:<8} {conf or 0:>7.1%}  {bar}")
