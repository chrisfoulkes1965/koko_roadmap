from __future__ import annotations
import os
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for, render_template_string
import pandas as pd

from excel_dal import (
    EXCEL_PATH, ensure_workbook,
    read_goals, read_relationships,
    update_goal, add_goal, delete_goal,
    toggle_link_goal,
    WriteLockedError
)

from changelog_dal import read_changelog

app = Flask(__name__)


@app.errorhandler(WriteLockedError)
def handle_write_locked_error(e):
    """Handle file lock errors with a user-friendly message."""
    return render_template_string("""
    {% extends 'base.html' %}
    {% block content %}
    <div style="padding: 2rem; max-width: 600px; margin: 0 auto;">
        <h2>File Locked</h2>
        <p style="color: #d32f2f; font-size: 1.1em; margin: 1rem 0;">
            {{ error_message }}
        </p>
        <p>Please:</p>
        <ul>
            <li>Close Microsoft Excel if you have <code>roadmap.xlsx</code> open</li>
            <li>Close any other programs that might be using the file</li>
            <li>Wait a few seconds and refresh this page</li>
        </ul>
        <div style="margin-top: 2rem;">
            <a href="{{ url_for('home') }}" class="btn primary">Go to Home</a>
            <button onclick="window.location.reload()" class="btn">Retry</button>
        </div>
    </div>
    {% endblock %}
    """, error_message=str(e)), 423


@app.get('/__routes')
def __routes():
    return '<pre>' + '\n'.join(sorted(str(r) for r in app.url_map.iter_rules())) + '</pre>'


@app.before_request
def _ensure_xlsx():
    ensure_workbook()

def _fmt_date_only(x):
    if x in (None, '', pd.NaT):
        return ''
    try:
        d = pd.to_datetime(x, errors='coerce')
        if pd.isna(d): return ''
        return d.date().isoformat()
    except Exception:
        return ''

@app.context_processor
def inject_excel_path():
    return dict(excel_path=str(Path(EXCEL_PATH).resolve()))


@app.get('/')
def home():
    # If you're using changelog_dal.py, prefer: from changelog_dal import read_changelog
    # and call that instead of reading directly.
    csv_path = Path(os.environ.get("KOKO_ROADMAP_CHANGELOG", "changelog.csv"))
    if not csv_path.exists():
        rows = []
    else:
        df = pd.read_csv(csv_path)
        # normalise column names
        cols = {c.lower(): c for c in df.columns}
        # pick a sortable date col
        if 'timestamp' in cols:
            sortcol = cols['timestamp']
        elif 'date' in cols:
            sortcol = cols['date']
        else:
            sortcol = None
        if sortcol:
            df['_sort'] = pd.to_datetime(df[sortcol], errors='coerce')
            df = df.sort_values('_sort', ascending=False).drop(columns=['_sort'])
        rows = df.to_dict(orient='records')

    return render_template('index.html', changelog=rows)


@app.get('/goals')
def goals():
    gs = read_goals().copy()
    # Show ALL goals by default - no filtering
    # Filter out rows where id is NaN or None
    if not gs.empty:
        gs = gs[gs['id'].notna()]
    rels = read_relationships()
    
    # Build parent/child relationships
    children_by_parent = {}
    parents_by_child = {}
    if not rels.empty:
        for _, r in rels.iterrows():
            parent_id = r.get('parent_id')
            child_id = r.get('child_id')
            if pd.notna(parent_id) and pd.notna(child_id):
                parent_id = int(parent_id)
                child_id = int(child_id)
                if parent_id not in children_by_parent:
                    children_by_parent[parent_id] = []
                children_by_parent[parent_id].append(child_id)
                if child_id not in parents_by_child:
                    parents_by_child[child_id] = []
                parents_by_child[child_id].append(parent_id)
    
    # Build goal lookup
    goal_by_id = {}
    if not gs.empty:
        for _, r in gs.iterrows():
            goal_id = int(r['id'])
            goal_by_id[goal_id] = r.get('name', '')
    
    rows = []
    for _, r in gs.iterrows():
        try:
            goal_id = r.get('id')
            if pd.isna(goal_id) or goal_id is None:
                continue
            goal_id = int(goal_id)
            display_val = r.get('display')
            # Convert to Yes/No: 1 or NaN = Yes, 0 = No
            display_text = 'No' if (pd.notna(display_val) and int(display_val) == 0) else 'Yes'
            
            # Get children and parents
            children_ids = children_by_parent.get(goal_id, [])
            children_names = [goal_by_id.get(cid, '') for cid in children_ids if cid in goal_by_id]
            parent_ids = parents_by_child.get(goal_id, [])
            parent_names = [goal_by_id.get(pid, '') for pid in parent_ids if pid in goal_by_id]
            
            rows.append(dict(
                id=goal_id,
                name=r.get('name',''),
                start_date=r.get('start_date',''),
                start_date_disp=_fmt_date_only(r.get('start_date','')),
                due_date=r.get('due_date',''),
                due_date_disp=_fmt_date_only(r.get('due_date','')),
                description='' if (pd.isna(r.get('description')) or str(r.get('description')).lower()=='nan') else r.get('description',''),
                display=display_text,
                display_value=int(display_val) if pd.notna(display_val) else 1,  # For form submission
                tags=r.get('tags', '') if pd.notna(r.get('tags')) else '',
                children_names=sorted([t for t in children_names if t]),
                parent_names=sorted([t for t in parent_names if t])
            ))
        except Exception as e:
            # Skip rows with errors, but log them
            import sys
            print(f"Error processing goal row: {e}", file=sys.stderr)
            continue
    
    # Get all goals for parent/child selection
    all_goals = []
    if not gs.empty:
        for _, r in gs.iterrows():
            goal_id = r.get('id')
            if pd.notna(goal_id):
                all_goals.append(dict(id=int(goal_id), name=r.get('name','')))
    
    return render_template('goals.html', goals=rows, all_goals=all_goals)


@app.get('/mindmap')
def mindmap():
    # Data
    gs = read_goals()
    # Filter out goals where display is explicitly 0 (No), but keep NaN/null (default to Yes)
    gs = gs[(gs['display'].isna()) | (gs['display'] != 0)]
    rels = read_relationships()

    # Goals payload
    goals_rows = [] if gs.empty else [
        dict(id=int(r['id']), name=r.get('name',''), due=_fmt_date_only(r.get('due_date','')), 
             start=_fmt_date_only(r.get('start_date','')), tags=r.get('tags','') if pd.notna(r.get('tags')) else '')
        for _, r in gs.iterrows()
    ]

    # Edges for hierarchical flow: parent → child relationships
    edges = []
    if not rels.empty:
        for _, r in rels.iterrows():
            parent_id = r.get('parent_id')
            child_id = r.get('child_id')
            if pd.notna(parent_id) and pd.notna(child_id):
                edges.append(dict(parent=int(parent_id), child=int(child_id)))

    payload = dict(
        goals=goals_rows,
        edges=edges
    )
    return render_template('mindmap.html', data=payload)


@app.get('/gantt')
def gantt():
    # Data
    gs = read_goals()
    # Filter out goals where display is explicitly 0 (No), but keep NaN/null (default to Yes)
    gs = gs[(gs['display'].isna()) | (gs['display'] != 0)]
    rels = read_relationships()

    # Helpers
    def _iso(x):  # ISO date ('' if blank/invalid)
        return _fmt_date_only(x)

    # Goals payload with dates
    goals_rows = [] if gs.empty else [
        dict(
            id=int(r['id']), 
            name=r.get('name',''), 
            start=_iso(r.get('start_date','')), 
            due=_iso(r.get('due_date','')), 
            tags=r.get('tags','') if pd.notna(r.get('tags')) else ''
        )
        for _, r in gs.iterrows()
    ]

    # Build parent-child relationships for grouping
    children_by_parent = {}
    parent_by_child = {}
    if not rels.empty:
        for _, r in rels.iterrows():
            parent_id = r.get('parent_id')
            child_id = r.get('child_id')
            if pd.notna(parent_id) and pd.notna(child_id):
                parent_id = int(parent_id)
                child_id = int(child_id)
                if parent_id not in children_by_parent:
                    children_by_parent[parent_id] = []
                children_by_parent[parent_id].append(child_id)
                parent_by_child[child_id] = parent_id

    payload = dict(
        goals=goals_rows,
        relationships=dict(
            children_by_parent=children_by_parent,
            parent_by_child=parent_by_child
        )
    )
    return render_template('gantt.html', data=payload)


@app.get('/sankey')
def sankey():
    # Data
    gs = read_goals()
    # Filter out goals where display is explicitly 0 (No), but keep NaN/null (default to Yes)
    gs = gs[(gs['display'].isna()) | (gs['display'] != 0)]
    rels = read_relationships()

    # Helpers
    def _iso(x):  # ISO date ('' if blank/invalid)
        return _fmt_date_only(x)

    # Goals payload
    goals_rows = [] if gs.empty else [
        dict(id=int(r['id']), name=r.get('name',''), due=_iso(r.get('due_date','')), tags=r.get('tags','') if pd.notna(r.get('tags')) else '')
        for _, r in gs.iterrows()
    ]

    # Edges for hierarchical flow: parent → child relationships
    edges = []
    if not rels.empty:
        for _, r in rels.iterrows():
            parent_id = r.get('parent_id')
            child_id = r.get('child_id')
            if pd.notna(parent_id) and pd.notna(child_id):
                edges.append(dict(parent=int(parent_id), child=int(child_id)))

    # Extract unique tags from all goals
    all_tags = set()
    if not gs.empty:
        for _, r in gs.iterrows():
            tags_str = r.get('tags', '')
            if pd.notna(tags_str) and tags_str:
                # Split by comma and clean up
                tags = [t.strip() for t in str(tags_str).split(',') if t.strip()]
                all_tags.update(tags)
    
    tags_list = sorted(list(all_tags))

    payload = dict(
        goals=goals_rows,
        edges=edges,
        tags=tags_list
    )
    height = int(request.args.get('h', '900'))
    return render_template('sankey.html', data=payload, height=height)


# ----- Linking UIs -----
@app.get('/links/goal/<int:goal_id>')
def links_goal(goal_id: int):
    gs = read_goals()
    rels = read_relationships()
    g = gs[gs['id']==goal_id]
    if g.empty: return redirect(url_for('goals'))
    
    # Get current children
    linked_children = set()
    if not rels.empty:
        linked_children = set(rels[rels['parent_id']==goal_id]['child_id'].tolist())
    
    # Get all goals except self
    all_goals = gs[gs['id'] != goal_id].sort_values(['name']).to_dict(orient='records')
    
    return render_template_string("""
    {% extends 'base.html' %}{% block content %}
    <h2>Link Children to Goal: {{ g.name }}</h2>
    <form method="post">
      {% for r in rows %}
        <div><label><input type="checkbox" name="child_id" value="{{ r.id }}" {% if r.id in linked %}checked{% endif %}> {{ r.name }}</label></div>
      {% endfor %}
      <div class="actions" style="margin-top:.75rem"><button class="btn primary">Save</button></div>
    </form>
    {% endblock %}
    """, g=dict(id=int(g.iloc[0]['id']), name=g.iloc[0]['name']), rows=all_goals, linked=linked_children)

@app.post('/links/goal/<int:goal_id>')
def links_goal_post(goal_id: int):
    gs = read_goals()
    submitted = set([int(x) for x in request.form.getlist('child_id')])
    all_ids = set(gs['id'].tolist()) if not gs.empty else set()
    # Remove self from all_ids
    all_ids.discard(goal_id)
    for child_id in all_ids:
        toggle_link_goal(goal_id, child_id, child_id in submitted)
    return redirect(url_for('goals'))

@app.get('/links/parents/<int:goal_id>')
def links_parents(goal_id: int):
    gs = read_goals()
    rels = read_relationships()
    g = gs[gs['id']==goal_id]
    if g.empty: return redirect(url_for('goals'))
    
    # Get current parents
    linked_parents = set()
    if not rels.empty:
        linked_parents = set(rels[rels['child_id']==goal_id]['parent_id'].tolist())
    
    # Get all goals except self
    all_goals = gs[gs['id'] != goal_id].sort_values(['name']).to_dict(orient='records')
    
    return render_template_string("""
    {% extends 'base.html' %}{% block content %}
    <h2>Link Parents to Goal: {{ g.name }}</h2>
    <form method="post">
      {% for r in rows %}
        <div><label><input type="checkbox" name="parent_id" value="{{ r.id }}" {% if r.id in linked %}checked{% endif %}> {{ r.name }}</label></div>
      {% endfor %}
      <div class="actions" style="margin-top:.75rem"><button class="btn primary">Save</button></div>
    </form>
    {% endblock %}
    """, g=dict(id=int(g.iloc[0]['id']), name=g.iloc[0]['name']), rows=all_goals, linked=linked_parents)

@app.post('/links/parents/<int:goal_id>')
def links_parents_post(goal_id: int):
    gs = read_goals()
    submitted = set([int(x) for x in request.form.getlist('parent_id')])
    all_ids = set(gs['id'].tolist()) if not gs.empty else set()
    # Remove self from all_ids
    all_ids.discard(goal_id)
    for parent_id in all_ids:
        toggle_link_goal(parent_id, goal_id, parent_id in submitted)
    return redirect(url_for('goals'))


# ----- Quick Add Parent/Child endpoints -----
@app.post('/goals/<int:goal_id>/add-parent/<int:parent_id>')
def goals_add_parent(goal_id: int, parent_id: int):
    """Add a single parent relationship."""
    gs = read_goals()
    # Validate that both goals exist
    if gs.empty or goal_id not in gs['id'].values or parent_id not in gs['id'].values:
        return jsonify(ok=False, error='Invalid goal ID'), 400
    # Prevent self-reference
    if goal_id == parent_id:
        return jsonify(ok=False, error='A goal cannot be its own parent'), 400
    try:
        toggle_link_goal(parent_id, goal_id, True)
    except WriteLockedError as e:
        return jsonify(ok=False, error=str(e)), 423
    except Exception as e:
        return jsonify(ok=False, error=f'Unexpected: {e}'), 500
    return jsonify(ok=True), 200

@app.post('/goals/<int:goal_id>/add-child/<int:child_id>')
def goals_add_child(goal_id: int, child_id: int):
    """Add a single child relationship."""
    gs = read_goals()
    # Validate that both goals exist
    if gs.empty or goal_id not in gs['id'].values or child_id not in gs['id'].values:
        return jsonify(ok=False, error='Invalid goal ID'), 400
    # Prevent self-reference
    if goal_id == child_id:
        return jsonify(ok=False, error='A goal cannot be its own child'), 400
    try:
        toggle_link_goal(goal_id, child_id, True)
    except WriteLockedError as e:
        return jsonify(ok=False, error=str(e)), 423
    except Exception as e:
        return jsonify(ok=False, error=f'Unexpected: {e}'), 500
    return jsonify(ok=True), 200

@app.post('/goals/<int:goal_id>/create-and-link-parent')
def goals_create_and_link_parent(goal_id: int):
    """Create a new goal and link it as a parent of the given goal."""
    name = _get('name')
    if not name:
        return jsonify(ok=False, error='Name is required.'), 400
    start = _get('start_date')
    due = _get('due_date')
    desc = _get('description')
    display_raw = _get('display')
    tags = _get('tags')
    display = None
    if display_raw and display_raw.lstrip('-').isdigit():
        display = int(display_raw)
    try:
        # Create the new goal
        parent_id = add_goal(name, due, desc, display, tags, start)
        # Link it as parent
        toggle_link_goal(parent_id, goal_id, True)
    except WriteLockedError as e:
        return jsonify(ok=False, error=str(e)), 423
    except Exception as e:
        return jsonify(ok=False, error=f'Unexpected: {e}'), 500
    return jsonify(ok=True, id=parent_id), 200

@app.post('/goals/<int:goal_id>/create-and-link-child')
def goals_create_and_link_child(goal_id: int):
    """Create a new goal and link it as a child of the given goal."""
    name = _get('name')
    if not name:
        return jsonify(ok=False, error='Name is required.'), 400
    start = _get('start_date')
    due = _get('due_date')
    desc = _get('description')
    display_raw = _get('display')
    tags = _get('tags')
    display = None
    if display_raw and display_raw.lstrip('-').isdigit():
        display = int(display_raw)
    try:
        # Create the new goal
        child_id = add_goal(name, due, desc, display, tags, start)
        # Link it as child
        toggle_link_goal(goal_id, child_id, True)
    except WriteLockedError as e:
        return jsonify(ok=False, error=str(e)), 423
    except Exception as e:
        return jsonify(ok=False, error=f'Unexpected: {e}'), 500
    return jsonify(ok=True, id=child_id), 200


# ----- Inline EDIT endpoints -----
def _get(field: str, default: str = '') -> str:
    if request.is_json:
        data = request.get_json(silent=True) or {}
        return (data.get(field, default) or '').strip()
    return (request.form.get(field, default) or '').strip()

@app.route('/goals/<int:goal_id>/edit-inline', methods=['POST'])
def goals_edit_inline(goal_id: int):
    name = _get('name'); start = _get('start_date'); due = _get('due_date'); desc = _get('description'); display_raw = _get('display'); tags = _get('tags')
    if not name: return jsonify(ok=False, error='Name is required.'), 400
    display = None
    if display_raw and display_raw.lstrip('-').isdigit():
        display = int(display_raw)
    try:
        update_goal(goal_id, name, due, desc, display, tags, start)
    except WriteLockedError as e: return jsonify(ok=False, error=str(e)), 423
    except Exception as e: return jsonify(ok=False, error=f'Unexpected: {e}'), 500
    return jsonify(ok=True), 200


@app.post('/goals/<int:goal_id>/delete-inline')
def goals_delete_inline(goal_id: int):
    rels = read_relationships()
    # Check if goal has children or is a child
    if not rels.empty:
        has_children = (rels['parent_id'] == int(goal_id)).any()
        is_child = (rels['child_id'] == int(goal_id)).any()
        if has_children or is_child:
            return jsonify(ok=False, error='Cannot delete: goal is linked to other goals as parent or child.'), 400
    try:
        delete_goal(goal_id)
    except WriteLockedError as e:
        return jsonify(ok=False, error=str(e)), 423
    except Exception as e:
        return jsonify(ok=False, error=f'Unexpected: {e}'), 500
    return jsonify(ok=True), 200

# ----- Inline ADD endpoints -----
@app.post('/goals/add-inline')
def goals_add_inline():
    name = _get('name'); start = _get('start_date'); due = _get('due_date'); desc = _get('description'); display_raw = _get('display'); tags = _get('tags')
    if not name: return jsonify(ok=False, error='Name is required.'), 400
    display = None
    if display_raw and display_raw.lstrip('-').isdigit():
        display = int(display_raw)
    try:
        new_id = add_goal(name, due, desc, display, tags, start)
    except WriteLockedError as e: return jsonify(ok=False, error=str(e)), 423
    except Exception as e: return jsonify(ok=False, error=f'Unexpected: {e}'), 500
    return jsonify(ok=True, id=new_id), 200

if __name__ == '__main__':
    # For local development
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
