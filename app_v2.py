from app import create_app

# Pre-import heavy PDF libs so Flask watchdog doesn't restart mid-request
import reportlab.platypus  # noqa: F401
import reportlab.lib.pagesizes  # noqa: F401
import xml.etree.ElementTree  # noqa: F401
import html.parser  # noqa: F401

app = create_app()

# Apply any pending DB migrations automatically on startup
with app.app_context():
    from flask_migrate import upgrade as _db_upgrade
    _db_upgrade()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True,
            extra_files=[], reloader_type="stat")
