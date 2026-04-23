"""
Return the set of job IDs already processed (applied, skipped, or attempted).
Usage: python tools/check_already_applied.py
       Or import: from tools.check_already_applied import get_applied_ids
"""
import json
from pathlib import Path

INDEX_PATH = Path("applied/index.json")


def get_applied_ids() -> set[str]:
    if not INDEX_PATH.exists():
        return set()
    with open(INDEX_PATH) as f:
        data = json.load(f)
    return set(data.keys())


if __name__ == "__main__":
    ids = get_applied_ids()
    print(f"Already processed job IDs ({len(ids)} total):")
    for job_id in sorted(ids):
        print(f"  {job_id}")
