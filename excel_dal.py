from __future__ import annotations
import os
from pathlib import Path
import pandas as pd

EXCEL_PATH = os.environ.get('KOKO_ROADMAP_XLSX', 'roadmap.xlsx')

class WriteLockedError(Exception):
    pass

def _safe_to_excel(writer, sheet_name: str, df: pd.DataFrame):
    """Write without NaN/NaT strings; keep blanks empty."""
    df2 = df.copy()
    for c in df2.columns:
        df2[c] = df2[c].apply(lambda v: None if (pd.isna(v) or str(v).lower() == 'nan') else v)
    df2.to_excel(writer, sheet_name=sheet_name, index=False)

def ensure_workbook():
    p = Path(EXCEL_PATH)
    if not p.exists():
        with pd.ExcelWriter(EXCEL_PATH, engine='openpyxl') as w:
            _safe_to_excel(w, 'goals', pd.DataFrame(columns=['id','name','due_date','description','display','tags']))
            _safe_to_excel(w, 'relationships', pd.DataFrame(columns=['parent_id','child_id']))
            _safe_to_excel(w, 'changelog', pd.DataFrame(columns=['date','version','note','author']))

def _read_sheet(name: str) -> pd.DataFrame:
    ensure_workbook()
    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name=name, engine='openpyxl')
    except PermissionError as e:
        raise WriteLockedError("roadmap.xlsx is locked by another application. Close it and try again.") from e
    except ValueError:
        # Try case-insensitive match first
        try:
            import openpyxl
            wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True)
            sheet_names = wb.sheetnames
            wb.close()
            # Find case-insensitive match
            matched_name = None
            for sheet_name in sheet_names:
                if sheet_name.lower() == name.lower():
                    matched_name = sheet_name
                    break
            if matched_name:
                df = pd.read_excel(EXCEL_PATH, sheet_name=matched_name, engine='openpyxl')
            else:
                # Create empty sheet if not found
                with pd.ExcelWriter(EXCEL_PATH, engine='openpyxl', mode='a', if_sheet_exists='overlay') as w:
                    _safe_to_excel(w, name, pd.DataFrame())
                df = pd.read_excel(EXCEL_PATH, sheet_name=name, engine='openpyxl')
        except Exception:
            # Fallback: create empty sheet
            with pd.ExcelWriter(EXCEL_PATH, engine='openpyxl', mode='a', if_sheet_exists='overlay') as w:
                _safe_to_excel(w, name, pd.DataFrame())
            df = pd.read_excel(EXCEL_PATH, sheet_name=name, engine='openpyxl')
    return df

def _write_sheet(name: str, df: pd.DataFrame):
    try:
        with pd.ExcelWriter(EXCEL_PATH, engine='openpyxl', mode='a', if_sheet_exists='replace') as w:
            _safe_to_excel(w, name, df)
    except PermissionError as e:
        raise WriteLockedError("roadmap.xlsx is locked by another application. Close it and try again.") from e

# ----- READERS -----

def read_changelog() -> pd.DataFrame:
    df = _read_sheet('changelog')
    # normalise expected columns
    for c in ['date','version','note','author']:
        if c not in df.columns: df[c] = None
    return df

def read_goals() -> pd.DataFrame:
    df = _read_sheet('goals')
    # Normalize column names to lowercase for case-insensitive matching
    df.columns = df.columns.astype(str).str.lower()
    for c in ['id','name','start_date','due_date','description','display','tags']:
        if c not in df.columns: df[c] = None
    # Convert display column to numeric, preserving 0 values and NaN (which means default Yes)
    if 'display' in df.columns:
        # Convert to numeric, coercing errors to NaN
        df['display'] = pd.to_numeric(df['display'], errors='coerce')
        # Don't fill NaN - keep it as NaN (means default Yes, but not explicitly set)
        # Only convert non-NaN values to int
        mask = df['display'].notna()
        df.loc[mask, 'display'] = df.loc[mask, 'display'].astype(int)
    else:
        df['display'] = pd.NA  # Use pd.NA to indicate not set (defaults to Yes)
    return df

def read_relationships() -> pd.DataFrame:
    df = _read_sheet('relationships')
    # Normalize column names to lowercase
    df.columns = df.columns.astype(str).str.lower()
    for c in ['parent_id','child_id']:
        if c not in df.columns: df[c] = None
    return df

# ----- UPDATERS -----

def update_goal(goal_id: int, name: str, due_date: str, description: str, display: int | None = None, tags: str | None = None, start_date: str | None = None):
    df = read_goals()
    idx = df.index[df['id'] == int(goal_id)]
    if len(idx) == 0: raise ValueError(f'Goal id {goal_id} not found')
    df.loc[idx, 'name'] = name
    if start_date is not None:
        if start_date:
            d = pd.to_datetime(start_date, errors='coerce')
            df.loc[idx, 'start_date'] = ('' if pd.isna(d) else d.date().isoformat())
        else:
            df.loc[idx, 'start_date'] = ''
    if due_date:
        d = pd.to_datetime(due_date, errors='coerce')
        df.loc[idx, 'due_date'] = ('' if pd.isna(d) else d.date().isoformat())
    else:
        df.loc[idx, 'due_date'] = ''
    df.loc[idx, 'description'] = description
    if display is not None:
        df.loc[idx, 'display'] = int(display)
    if tags is not None:
        df.loc[idx, 'tags'] = tags
    _write_sheet('goals', df)

# ----- CREATORS -----

def add_goal(name: str, due_date: str | None, description: str, display: int | None = None, tags: str | None = None, start_date: str | None = None):
    df = read_goals()
    next_id = (int(df['id'].max()) + 1) if not df.empty and df['id'].notna().any() else 1
    rec = {'id': next_id, 'name': name}
    if start_date:
        d = pd.to_datetime(start_date, errors='coerce')
        rec['start_date'] = ('' if pd.isna(d) else d.date().isoformat())
    else:
        rec['start_date'] = ''
    if due_date:
        d = pd.to_datetime(due_date, errors='coerce')
        rec['due_date'] = ('' if pd.isna(d) else d.date().isoformat())
    else:
        rec['due_date'] = ''
    rec['description'] = description
    rec['display'] = int(display) if display is not None else 1  # Default to visible
    rec['tags'] = tags if tags is not None else ''
    df = pd.concat([df, pd.DataFrame([rec])], ignore_index=True)
    _write_sheet('goals', df)
    return next_id

# ----- DELETERS -----

def delete_goal(goal_id: int):
    df = read_goals()
    idx = df.index[df['id'] == int(goal_id)]
    if len(idx) == 0:
        raise ValueError(f'Goal id {goal_id} not found')
    df = df.drop(index=idx)
    _write_sheet('goals', df)

# ----- RELATIONSHIP TOGGLERS -----

def toggle_link_goal(parent_id: int, child_id: int, enabled: bool):
    df = read_relationships()
    mask = (df['parent_id'] == int(parent_id)) & (df['child_id'] == int(child_id))
    exists = df[mask]
    changed = False
    if enabled and exists.empty:
        df = pd.concat([df, pd.DataFrame([{'parent_id': int(parent_id), 'child_id': int(child_id)}])], ignore_index=True)
        changed = True
    if (not enabled) and not exists.empty:
        df = df.drop(exists.index)
        changed = True
    if changed:
        _write_sheet('relationships', df)
