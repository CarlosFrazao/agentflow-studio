"""TDD FEAT-005: classificacao de licenca sem falso-positivo (P1-4).

Cobre o ADR de word-boundary + contexto de licenca: texto que *menciona*
"GPL" numa comparacao NAO deve virar copyleft, mas AGPL/LGPL/GPL reais sim.
"""

import pytest

from app.services.agents.code_research import CodeResearchAgent


def test_classify_mit_not_copyleft() -> None:
    cls = CodeResearchAgent._classify_license("MIT License\nPermission is hereby granted...")
    assert cls == "permissive"


def test_license_mention_not_copyleft() -> None:
    # "GPL" aparece solto numa comparacao, longe de qualquer contexto de
    # licenca -> NAO deve classificar copyleft.
    text = (
        "Our benchmark shows this library is faster than the old GPL-based "
        "implementation, which is why we rewrote it from scratch."
    )
    cls = CodeResearchAgent._classify_license(text)
    assert cls != "copyleft"


def test_license_real_agpl_copyleft() -> None:
    text = (
        "                    GNU AFFERO GENERAL PUBLIC LICENSE\n"
        "Version 3, 19 November 2007"
    )
    cls = CodeResearchAgent._classify_license(text)
    assert cls == "copyleft"


def test_license_real_lgpl_copyleft() -> None:
    text = (
        "    GNU LESSER GENERAL PUBLIC LICENSE\n"
        "Version 2.1, February 1999"
    )
    cls = CodeResearchAgent._classify_license(text)
    assert cls == "copyleft"


def test_license_real_gpl_copyleft() -> None:
    text = (
        "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007"
    )
    cls = CodeResearchAgent._classify_license(text)
    assert cls == "copyleft"


def test_classify_short_gpl_token_copyleft() -> None:
    # Sigla isolada com contexto de licenca (SPDX/GPL-3.0) = copyleft.
    cls = CodeResearchAgent._classify_license("License: GPL-3.0-or-later")
    assert cls == "copyleft"
