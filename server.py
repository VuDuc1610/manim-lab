import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from webapp.app import create_app

if __name__ == "__main__":
    create_app().run(port=5000, debug=True, use_reloader=False)
