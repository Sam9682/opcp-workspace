"""Bug condition exploration test for the config unterminated-string crash.

Spec: .kiro/specs/config-unterminated-string-crash/

This test encodes the EXPECTED (fixed) behavior for the bug condition. It is
written BEFORE the fix and is EXPECTED TO FAIL on the unfixed code -- its
failure confirms the bug exists.

Bug condition (isBugCondition):
  isBugCondition(source) = hasUnterminatedTripleQuotedString(source)
  True when a ``LegalDocument`` ``content`` field opens a ``\"\"\"`` triple-quoted
  string that is never closed before the constructor's closing ``)`` in
  ``app/info/config.py`` (this happens for both ``STATUTES.content`` and
  ``REGULATIONS.content``).

Property 1 (Bug Condition - Module Parses and Imports Cleanly):
  For the module source where the bug condition holds, the fixed module SHALL
  parse and import without raising ``SyntaxError``, with ``STATUTES.content`` and
  ``REGULATIONS.content`` each holding a fully terminated string value, allowing
  the import chain (``app.main`` -> ``app.info.router`` -> ``app.info.config``)
  to complete and uvicorn to load the FastAPI app.

Validates: Requirements 1.1, 1.2, 1.3 (2.1, 2.2, 2.3 after fix)

Scoped PBT approach: the parse failure is deterministic, so the
"for all sources where isBugCondition(source)" quantifier collapses to the one
concrete failing input -- the current text of ``app/info/config.py``.

DO NOT "fix" this test when it fails on unfixed code -- the failure IS the
expected outcome and documents the bug.
"""
import subprocess
import sys
from pathlib import Path

import pytest

# Repository root: tests/ lives directly under the project root.
REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "app" / "info" / "config.py"


def _run(args):
    """Run a python subprocess from the repo root and capture its result.

    Running in a child process isolates the (currently unparseable) module so a
    SyntaxError surfaces as a nonzero exit + stderr rather than aborting the
    test collector. The repo root is the CWD so ``import app.*`` resolves.
    """
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


# --------------------------------------------------------------------------
# Test case 1: byte-compile the module.
#
# EXPECTED-ON-FIX: py_compile succeeds (exit 0, no SyntaxError).
# On UNFIXED code this fails with
#   "SyntaxError: unterminated string literal (detected at line 71)"
# which confirms the bug.
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_config_module_byte_compiles():
    """`python -m py_compile app/info/config.py` must succeed with no SyntaxError."""
    result = _run(["-m", "py_compile", str(CONFIG_PATH)])
    assert result.returncode == 0, (
        "Byte-compiling app/info/config.py should succeed after the fix, but it "
        f"failed.\nstderr:\n{result.stderr}"
    )
    assert "SyntaxError" not in result.stderr, (
        f"Unexpected SyntaxError while byte-compiling config.py:\n{result.stderr}"
    )
    assert "unterminated string literal" not in result.stderr, (
        f"Unterminated string literal detected in config.py:\n{result.stderr}"
    )


# --------------------------------------------------------------------------
# Test case 2: direct import of the module, then assert the two content strings
# are fully terminated (non-None str values).
#
# EXPECTED-ON-FIX: clean import; STATUTES.content and REGULATIONS.content are
# non-empty str. On UNFIXED code the import raises the SyntaxError.
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_config_module_imports_with_terminated_content_strings():
    """Import app.info.config; STATUTES.content / REGULATIONS.content are terminated str."""
    check = (
        "import app.info.config as c\n"
        "assert isinstance(c.STATUTES.content, str), 'STATUTES.content not a str'\n"
        "assert c.STATUTES.content, 'STATUTES.content is empty'\n"
        "assert isinstance(c.REGULATIONS.content, str), 'REGULATIONS.content not a str'\n"
        "assert c.REGULATIONS.content, 'REGULATIONS.content is empty'\n"
        "assert c.STATUTES.content.startswith(\"STATUTS DE L'OPCP\"), 'STATUTES header changed'\n"
        "assert c.REGULATIONS.content.startswith(\"RÈGLEMENT INTÉRIEUR DE L'OPCP\"), 'REGULATIONS header changed'\n"
        "print('OK')\n"
    )
    result = _run(["-c", check])
    assert result.returncode == 0, (
        "Importing app.info.config should succeed after the fix with terminated "
        f"content strings, but it failed.\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "SyntaxError" not in result.stderr, (
        f"Unexpected SyntaxError while importing config.py:\n{result.stderr}"
    )
    assert "OK" in result.stdout


# --------------------------------------------------------------------------
# Test case 3: import chain app.main -> app.info.router -> app.info.config.
#
# EXPECTED-ON-FIX: `import app.main` succeeds, so uvicorn can import the app.
# On UNFIXED code the parse error propagates through the chain and this fails.
# --------------------------------------------------------------------------
@pytest.mark.integration
def test_app_main_import_chain_completes():
    """`import app.main` must complete the chain without a SyntaxError."""
    result = _run(["-c", "import app.main; print('OK')"])
    assert result.returncode == 0, (
        "Importing app.main should complete the chain (app.main -> "
        "app.info.router -> app.info.config) after the fix, but it failed.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "SyntaxError" not in result.stderr, (
        f"Unexpected SyntaxError while importing app.main:\n{result.stderr}"
    )
    assert "OK" in result.stdout
