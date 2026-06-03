# Koush Workbench

The **Koush Workbench** (v1.6+) provides a local, statically generated UI dashboard over your cartridge. It runs entirely on your local machine using standard Python libraries—no external JS frameworks, no cloud connections, and no tracking.

## Usage

```bash
# Build the static HTML dashboard in `exports/workbench/`
koush workbench build

# Serve the dashboard locally
koush workbench serve --port 8765

# Build and immediately open in your default browser
koush workbench open

# Export the entire workbench to a zip file (ready for sharing/archiving)
koush workbench export

# Clean up generated files
koush workbench clean
```

## Privacy & Security

By default, the workbench **excludes all private and quarantined data**. Any memory items marked with `visibility: private`, `visibility: blocked`, or `visibility: quarantine` will not be included in the HTML or JSON exports.

To include private data (e.g. for your own local inspection only):
```bash
koush workbench build --include-private
```

When exporting, Koush defaults to a "safe" export (excluding private content). You can force it to export what is currently built by removing `--safe`.

## Generated Structure

The dashboard exports to `exports/workbench/`:
- `index.html` (Dashboard overview)
- `projects.html`
- `decisions.html`
- `search.html` (with a local text search index)
- `data/*.json` (JSON dumps of the state for programmatic access)

It is highly portable and can be zipped or hosted on any simple static file server.
