"""Import before psycopg: where Application Control blocks psycopg_binary, the embedded server's libpq is used."""
import os
from importlib.util import find_spec
from pathlib import Path

_spec = find_spec("pixeltable_pgserver")
if _spec:
    os.environ["PATH"] = f"{Path(_spec.origin).parent / 'pginstall' / 'bin'}{os.pathsep}{os.environ['PATH']}"
