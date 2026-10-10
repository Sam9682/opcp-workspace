"""Preservation property tests for the config unterminated-string crash.

Spec: .kiro/specs/config-unterminated-string-crash/

Property 2 (Preservation - Other Symbols and Fields Unchanged):
  For any module symbol where the bug condition does NOT hold (isBugCondition
  returns false -- the symbol is unrelated to the unterminated strings), the
  fixed module SHALL produce the same result as the original intended module,
  preserving the values and types of ``PSMC_INFO``, ``MISSION``, ``ACTIVITIES``,
  ``CONTACT_EMAIL``, ``CONTACT_PHONE``, ``FINANCIAL_REPORTS``,
  ``BOARD_LAST_UPDATED``, and the ``title``/``description`` fields of
  ``STATUTES`` and ``REGULATIONS``.

  Property (formal): FOR ALL preserved symbols, F(symbol) = F'(symbol)
  where F is the original intended module and F' is the fixed module.

Validates: Requirements 3.1, 3.2, 3.3, 3.4

------------------------------------------------------------------------------
OBSERVATION-FIRST METHODOLOGY / BASELINE NOTE
------------------------------------------------------------------------------
The unfixed module ``app/info/config.py`` CANNOT be imported at all: it is
unparseable because ``STATUTES.content`` and ``REGULATIONS.content`` open
triple-quoted strings that are never closed (``SyntaxError: unterminated string
literal (detected at line 71)``). Therefore the "observed" preservation values
cannot be taken from a live import of F -- instead they are recorded here from
the *intended, unambiguous literals* in the source (the values that are clearly
written and not part of the unterminated ``content`` bodies).

These recorded expectations (see ``EXPECTED_*`` below) FORM THE BASELINE to
preserve. On UNFIXED code, every test that imports the module is expected to
FAIL at import time with a SyntaxError -- that failure IS the documented
baseline. After the fix (task 3.3), these same tests import the live module and
assert each preserved symbol equals its recorded expected literal, confirming no
regression.

DO NOT weaken or "fix" these expectations to make them pass on unfixed code --
the import-time failure on unfixed code is the expected baseline.
"""
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

# Repository root: tests/ lives directly under the project root.
REPO_ROOT = Path(__file__).resolve().parent.parent


# ==========================================================================
# RECORDED BASELINE -- intended literal values observed from the source of
# app/info/config.py (F, the original intended module). These are the values
# that must be PRESERVED by the fix (F' must equal F for each of these).
#
# NOTE: These are the exact literals written in the source, excluding the two
# unterminated `content` bodies which are the bug fields (not preserved here).
# ==========================================================================

EXPECTED_CONTACT_EMAIL = "contact@opcp-psmc.com"
EXPECTED_CONTACT_PHONE = "+33 1 23 45 67 89"

EXPECTED_BOARD_LAST_UPDATED = date(2024, 1, 15)

EXPECTED_MISSION = (
    "OPCP est produit OVH dédiée à la promotion et au développement \n"
    "des technologies de l'information et de la communication. Notre mission est de créer un espace \n"
    "d'échange et de partage de connaissances pour tous les passionnés de technologie."
)

EXPECTED_ACTIVITIES = (
    "Nos activités incluent :\n"
    "- Organisation de conférences et d'ateliers techniques\n"
    "- Mise en place de groupes de travail thématiques\n"
    "- Développement de projets collaboratifs open source\n"
    "- Événements de networking pour les membres\n"
    "- Formation continue et partage de compétences\n"
    "- Participation à des événements communautaires"
)

# PSMC_INFO intended values (PSMCInfo + BoardMember objects).
EXPECTED_PSMC_INFO = {
    "name": "OPCP",
    "address": "123 Rue de l'PSMC, 75001 Paris, France",
    "siret": "12345678900012",
    "board_members": [
        {"name": "Jean Dupont", "position": "Président", "email": "president@opcp-psmc.com"},
        {"name": "Marie Martin", "position": "Trésorière", "email": "tresorier@opcp-psmc.com"},
        {"name": "Pierre Durand", "position": "Secrétaire", "email": "secretaire@opcp-psmc.com"},
    ],
}

# FINANCIAL_REPORTS intended values (list of FinancialReport objects).
EXPECTED_FINANCIAL_REPORTS = [
    {
        "id": "report-2024",
        "title": "Rapport Financier 2024",
        "year": 2024,
        "description": "Rapport financier annuel incluant le bilan et les notes explicatives.",
        "published_date": date(2024, 12, 31),
    },
    {
        "id": "report-2023",
        "title": "Rapport Financier 2023",
        "year": 2023,
        "description": "Rapport financier annuel incluant le bilan et les notes explicatives.",
        "published_date": date(2023, 12, 31),
    },
    {
        "id": "report-2022",
        "title": "Rapport Financier 2022",
        "year": 2022,
        "description": "Rapport financier annuel incluant le bilan et les notes explicatives.",
        "published_date": date(2022, 12, 31),
    },
]

# STATUTES / REGULATIONS title + description (the `content` bodies are the bug
# fields and are intentionally NOT part of the preserved baseline).
EXPECTED_STATUTES_TITLE = "Statuts de l'OPCP"
EXPECTED_STATUTES_DESCRIPTION = (
    "Les statuts définissent l'objet, le fonctionnement et les règles de la plateforme OPCP."
)
EXPECTED_REGULATIONS_TITLE = "Règlement Intérieur de l'OPCP"
EXPECTED_REGULATIONS_DESCRIPTION = (
    "Le règlement intérieur précise les modalités d'application des statuts "
    "et les règles de fonctionnement quotidien."
)

# The full set of preserved simple-valued symbols keyed by name. This drives the
# parametrized / property-style "for all preserved symbols" assertions.
PRESERVED_SCALAR_EXPECTATIONS = {
    "CONTACT_EMAIL": (EXPECTED_CONTACT_EMAIL, str),
    "CONTACT_PHONE": (EXPECTED_CONTACT_PHONE, str),
    "MISSION": (EXPECTED_MISSION, str),
    "ACTIVITIES": (EXPECTED_ACTIVITIES, str),
    "BOARD_LAST_UPDATED": (EXPECTED_BOARD_LAST_UPDATED, date),
}

# Symbols that must exist and resolve with a stable name/type through the
# downstream importer (app.info.router imports all of these).
ROUTER_RESOLVED_SYMBOLS = [
    "PSMC_INFO",
    "MISSION",
    "ACTIVITIES",
    "CONTACT_EMAIL",
    "CONTACT_PHONE",
    "STATUTES",
    "REGULATIONS",
    "FINANCIAL_REPORTS",
    "BOARD_LAST_UPDATED",
]


def _import_config():
    """Import app.info.config, adjusting sys.path to the repo root.

    On UNFIXED code this raises SyntaxError at import time -- that is the
    expected baseline for every test that calls this helper.
    """
    import importlib

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module("app.info.config")


def _run(args):
    """Run a python subprocess from the repo root and capture its result."""
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


# --------------------------------------------------------------------------
# Property 2 (preservation) -- scalar / string constants.
#
# For all preserved scalar symbols: F'(symbol) == recorded expected literal,
# and the type matches. On unfixed code this fails at import (SyntaxError).
# --------------------------------------------------------------------------
@pytest.mark.property
@pytest.mark.parametrize("symbol_name", sorted(PRESERVED_SCALAR_EXPECTATIONS))
def test_preserved_scalar_symbol_matches_baseline(symbol_name):
    """Each preserved scalar symbol equals its recorded expected literal and type.

    Validates: Requirements 3.1, 3.2
    """
    config = _import_config()
    expected_value, expected_type = PRESERVED_SCALAR_EXPECTATIONS[symbol_name]

    assert hasattr(config, symbol_name), f"config is missing symbol {symbol_name!r}"
    actual = getattr(config, symbol_name)
    assert isinstance(actual, expected_type), (
        f"{symbol_name} should be {expected_type.__name__}, got {type(actual).__name__}"
    )
    assert actual == expected_value, (
        f"{symbol_name} changed from its recorded baseline.\n"
        f"expected: {expected_value!r}\nactual:   {actual!r}"
    )


# --------------------------------------------------------------------------
# Property 2 (preservation) -- PSMC_INFO object graph.
# --------------------------------------------------------------------------
@pytest.mark.property
def test_preserved_psmc_info_matches_baseline():
    """PSMC_INFO preserves its name/address/siret and board members.

    Validates: Requirements 3.1
    """
    config = _import_config()
    psmc = config.PSMC_INFO

    assert psmc.name == EXPECTED_PSMC_INFO["name"]
    assert psmc.address == EXPECTED_PSMC_INFO["address"]
    assert psmc.siret == EXPECTED_PSMC_INFO["siret"]

    assert len(psmc.board_members) == len(EXPECTED_PSMC_INFO["board_members"])
    for actual_member, expected_member in zip(
        psmc.board_members, EXPECTED_PSMC_INFO["board_members"]
    ):
        assert actual_member.name == expected_member["name"]
        assert actual_member.position == expected_member["position"]
        assert actual_member.email == expected_member["email"]


# --------------------------------------------------------------------------
# Property 2 (preservation) -- FINANCIAL_REPORTS list.
# --------------------------------------------------------------------------
@pytest.mark.property
def test_preserved_financial_reports_match_baseline():
    """FINANCIAL_REPORTS preserves each report's fields, order and values.

    Validates: Requirements 3.1
    """
    config = _import_config()
    reports = config.FINANCIAL_REPORTS

    assert isinstance(reports, list)
    assert len(reports) == len(EXPECTED_FINANCIAL_REPORTS)
    for actual_report, expected_report in zip(reports, EXPECTED_FINANCIAL_REPORTS):
        assert actual_report.id == expected_report["id"]
        assert actual_report.title == expected_report["title"]
        assert actual_report.year == expected_report["year"]
        assert actual_report.description == expected_report["description"]
        assert actual_report.published_date == expected_report["published_date"]


# --------------------------------------------------------------------------
# Property 2 (preservation) -- STATUTES / REGULATIONS title & description.
# The `content` bodies are the bug fields and are intentionally excluded.
# --------------------------------------------------------------------------
@pytest.mark.property
def test_preserved_legal_document_metadata_matches_baseline():
    """STATUTES/REGULATIONS title and description are unchanged by the fix.

    Validates: Requirements 3.3
    """
    config = _import_config()

    assert config.STATUTES.title == EXPECTED_STATUTES_TITLE
    assert config.STATUTES.description == EXPECTED_STATUTES_DESCRIPTION
    assert config.REGULATIONS.title == EXPECTED_REGULATIONS_TITLE
    assert config.REGULATIONS.description == EXPECTED_REGULATIONS_DESCRIPTION


# --------------------------------------------------------------------------
# Property 2 (preservation) -- downstream resolution through app.info.router.
#
# app.info.router imports every config symbol; after the fix, importing the
# router must succeed and each symbol must resolve to the identical object
# with the same name and type as in app.info.config.
# --------------------------------------------------------------------------
@pytest.mark.property
def test_router_resolves_config_symbols_with_same_names_and_types():
    """app.info.router imports and resolves config symbols with same names/types.

    Validates: Requirements 3.4
    """
    check = (
        "import app.info.config as c\n"
        "import app.info.router as r\n"
        "names = " + repr(ROUTER_RESOLVED_SYMBOLS) + "\n"
        "for name in names:\n"
        "    assert hasattr(c, name), 'config missing ' + name\n"
        "    assert hasattr(r, name), 'router missing ' + name\n"
        "    cv = getattr(c, name)\n"
        "    rv = getattr(r, name)\n"
        "    assert rv is cv, 'router ' + name + ' is not the same object as config'\n"
        "    assert type(rv) is type(cv), 'router ' + name + ' type differs'\n"
        "print('OK')\n"
    )
    result = _run(["-c", check])
    assert result.returncode == 0, (
        "Importing app.info.router and resolving config symbols should succeed "
        f"after the fix.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "SyntaxError" not in result.stderr, (
        f"Unexpected SyntaxError resolving router symbols:\n{result.stderr}"
    )
    assert "OK" in result.stdout
