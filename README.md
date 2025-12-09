# KOKO Roadmap

A web-based roadmap management tool for visualizing and managing strategic goals and their relationships.

## Features

- 📊 **Sankey Diagram** - Visualize goal hierarchies with minimized crossings
- 🗺️ **Mind Map** - Interactive tree view of goal relationships
- 📋 **Goals Management** - Create, edit, and organize goals
- 🔗 **Relationship Management** - Link goals as parents and children
- 📅 **Date Tracking** - Start dates and due dates for goals
- 🏷️ **Tagging** - Organize goals with tags
- 📈 **Filtering** - Filter goals by tags and other criteria

## Quick Start

### Local Development

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the app**:
   ```bash
   python app.py
   ```

3. **Open in browser**:
   ```
   http://localhost:5000
   ```

### Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

**Quick deploy to Render.com**:
1. Push code to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your repo → Deploy
4. Share the URL with your team!

## Project Structure

```
koko_roadmap/
├── app.py              # Main Flask application
├── excel_dal.py        # Excel data access layer
├── changelog_dal.py    # Changelog data access
├── requirements.txt    # Python dependencies
├── roadmap.xlsx       # Data storage (Excel)
├── templates/         # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── goals.html
│   ├── sankey.html
│   └── mindmap.html
└── static/            # CSS and static files
    └── style.css
```

## Usage

### Creating Goals

1. Go to **Goals** page
2. Click **Add Goal**
3. Fill in name, dates, description, tags
4. Save

### Linking Goals

**From Sankey/Mind Map**:
- Click on any goal node
- Use **+ Add Parent** or **+ Add Child** to create and link new goals
- Use **Manage Parents/Children** to link existing goals

**From Goals Page**:
- Click **Add Parent** or **Add Child** buttons
- Choose to select existing goal or create new one

### Visualizations

- **Sankey Diagram**: Shows flow between goal levels, automatically minimizes line crossings
- **Mind Map**: Interactive tree view with zoom, pan, expand/collapse

## Data Storage

Currently uses Excel files (`roadmap.xlsx`) for storage. For production with multiple users, consider migrating to a database (SQLite for small teams, PostgreSQL for larger deployments).

## Environment Variables

- `KOKO_ROADMAP_XLSX` - Path to Excel file (default: `roadmap.xlsx`)
- `KOKO_ROADMAP_CHANGELOG` - Path to changelog CSV (default: `changelog.csv`)
- `PORT` - Server port (default: 5000)
- `FLASK_DEBUG` - Enable debug mode (default: False)

## License

Internal use only.

