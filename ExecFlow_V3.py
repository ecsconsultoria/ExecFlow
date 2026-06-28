import os
from app import create_app

# Pre-import heavy PDF libs only em dev (Flask watchdog).
# Em produção (gunicorn) NÃO pré-carregar: economiza ~30-50 MB do limite de 512 MB do Render.
if os.environ.get("FLASK_ENV", "").lower() in ("development", "dev", ""):
    import reportlab.platypus  # noqa: F401
    import reportlab.lib.pagesizes  # noqa: F401
    import xml.etree.ElementTree  # noqa: F401
    import html.parser  # noqa: F401

app = create_app()

# Apply any pending DB migrations automatically on startup
with app.app_context():
    from flask_migrate import upgrade as _db_upgrade
    _db_upgrade()

# Em prod: congela tudo que já foi importado/criado para fora do garbage collector.
# Reduz pressao de memoria e fragmentacao (helpful no Render Starter 512 MB).
if os.environ.get("FLASK_ENV", "").lower() == "production":
    import gc
    gc.collect()
    gc.freeze()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, debug=True,
            extra_files=[], reloader_type="stat")
