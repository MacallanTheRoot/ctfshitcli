"""
Entry point for the installed `ctf` command (CSL-CtfShitCli).

Uses importlib to load main.py from THIS package's own directory,
bypassing any sys.path ordering issues that would cause the wrong
`main` module to be imported when other packages define one too.
"""

import importlib.util
import os
import sys


def _bootstrap():
    """Load main.py from the same directory as this file, explicitly."""
    here = os.path.dirname(os.path.abspath(__file__))

    # Ensure src/ imports inside main.py resolve correctly
    if here not in sys.path:
        sys.path.insert(0, here)

    spec = importlib.util.spec_from_file_location(
        "ctfshit_main",
        os.path.join(here, "main.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ctfshit_main"] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    """Installed entry point — called by the `ctf` console script."""
    _bootstrap().cli(prog_name="ctf")


if __name__ == "__main__":
    main()
