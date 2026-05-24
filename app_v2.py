from app import create_app

# Pre-import heavy PDF libs so Flask watchdog doesn't restart mid-request
import reportlab.platypus  # noqa: F401
import reportlab.lib.pagesizes  # noqa: F401
import xml.etree.ElementTree  # noqa: F401
import html.parser  # noqa: F401

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, debug=True,
            extra_files=[], reloader_type="stat")
