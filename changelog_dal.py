# changelog_dal.py
import pandas as pd
from pathlib import Path

CHANGELOG_PATH = Path("changelog.csv")

def read_changelog():
    if not CHANGELOG_PATH.exists():
        return pd.DataFrame(columns=["timestamp","action","entity_type","entity_id","details"])
    df = pd.read_csv(CHANGELOG_PATH)
    return df.fillna("")

def append_changelog(action, entity_type, entity_id, details=""):
    df = read_changelog()
    new_row = {
        "timestamp": pd.Timestamp.now().isoformat(timespec="seconds"),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(CHANGELOG_PATH, index=False)
