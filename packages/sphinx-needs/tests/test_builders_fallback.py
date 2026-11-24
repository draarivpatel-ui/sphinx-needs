"""Builder regressions from https://github.com/useblocks/sphinx-needs/issues/2560.

Pages that build fine with ``html`` failed or warned wrongly with ``text``,
``epub`` and the other writers:

- an inline needs role in a title (``:need:``, ``:np:``) reached the ``text``
  writer in the copies Sphinx makes of the title for its tables of contents,
  where it was an unknown node,
- the ``epub`` builder met every other extension's html-only nodes as unknown
  nodes, because sphinx-data-viewer registering an ``epub`` visitor of its own
  stops Sphinx falling back to the html handlers for the rest,
- a part outside every need was reported once per resolved tree, so ``epub``
  (which resolves the root page again and again) repeated the finding, and on
  the builders that never resolve such a page it was never reported at all.
"""

import io
from pathlib import Path
from typing import Any

import pytest
from sphinx.application import Sphinx

from sphinx_needs_testkit import build_warnings

CONF = """\
project = "builders"
extensions = ["sphinx_needs"]
version = "1.0"
copyright = "the authors"
"""

#: a title holding each inline needs role, on a page its toctree lists, so the
#: writer meets the node in the title's table-of-contents copies
ROLES_IN_A_TITLE_INDEX = """\
Index
=====

.. toctree::

   page

.. req:: A requirement
   :id: REQ_1
"""

ROLES_IN_A_TITLE_PAGE = """\
Page :need:`REQ_1` and :np:`(p1) a part` in a title
==================================================

A section :np:`(p2) another part`
---------------------------------

Body text.
"""


@pytest.mark.parametrize("buildername", ["text", "man", "texinfo"])
def test_inline_roles_in_a_title_build(
    make_app: Any, tmp_path: Path, buildername: str
) -> None:
    """``:need:`` and ``:np:`` in titles reach no writer as unknown nodes."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(CONF, encoding="utf-8")
    (srcdir / "index.rst").write_text(ROLES_IN_A_TITLE_INDEX, encoding="utf-8")
    (srcdir / "page.rst").write_text(ROLES_IN_A_TITLE_PAGE, encoding="utf-8")

    app = make_app(
        buildername=buildername,
        srcdir=srcdir,
        builddir=tmp_path / "build" / buildername,
        freshenv=True,
        warning=io.StringIO(),
    )
    app.build()

    assert [w for w in build_warnings(app) if "unknown node type" in w] == []


#: an extension registering a node for ``html`` alone, as sphinx.ext.graphviz,
#: sphinxcontrib-plantuml and many others do
HTML_ONLY_NODE_EXT = """\
from docutils import nodes


class HtmlOnlyNode(nodes.Element):
    pass


def visit(self, node):
    self.body.append("<p>html only</p>")
    raise nodes.SkipNode


def depart(self, node):
    pass


def setup(app):
    app.add_node(HtmlOnlyNode, html=(visit, depart))
    app.add_directive("html-only", Directive)


from docutils.parsers.rst import Directive


class Directive(Directive):
    def run(self):
        return [HtmlOnlyNode("")]
"""

HTML_ONLY_NODE_INDEX = """\
Index
=====

.. html-only::
"""


def test_epub_falls_back_to_html_handlers(make_app: Any, tmp_path: Path) -> None:
    """The ``epub`` writer uses the ``html`` handlers of a node that has no
    ``epub`` ones, exactly as it does without sphinx-data-viewer.

    sphinx-needs loads sphinx-data-viewer, whose own ``epub`` visitor stops
    Sphinx applying its builder-format fallback to every other node.
    """
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        "import os\nimport sys\nsys.path.insert(0, os.path.dirname(__file__))\n"
        + CONF
        + 'extensions.append("html_only_node")\n',
        encoding="utf-8",
    )
    (srcdir / "html_only_node.py").write_text(HTML_ONLY_NODE_EXT, encoding="utf-8")
    (srcdir / "index.rst").write_text(HTML_ONLY_NODE_INDEX, encoding="utf-8")

    app = make_app(
        buildername="epub",
        srcdir=srcdir,
        builddir=tmp_path / "build" / "epub",
        freshenv=True,
        warning=io.StringIO(),
    )
    app.build()

    assert [w for w in build_warnings(app) if "unknown node type" in w] == []


LOOSE_PART_INDEX = """\
Index
=====

.. toctree::

   loose
"""

LOOSE_PART_PAGE = """\
Loose
=====

A :np:`(x1) loose part` outside every need.
"""

LOOSE_PART_WARNING = (
    "WARNING: Need part not associated with a need. [needs.part]"
)


def test_loose_part_on_a_needless_page_warns_once(
    make_app: Any, tmp_path: Path
) -> None:
    """A part on a page holding no need is reported once, on ``html`` too.

    The finding used to run only for pages sphinx-needs processes, so a page
    with a part and no need was never reported by the per-page builders.
    """
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(CONF, encoding="utf-8")
    (srcdir / "index.rst").write_text(LOOSE_PART_INDEX, encoding="utf-8")
    (srcdir / "loose.rst").write_text(LOOSE_PART_PAGE, encoding="utf-8")

    app = make_app(
        buildername="html",
        srcdir=srcdir,
        builddir=tmp_path / "build" / "html",
        freshenv=True,
        warning=io.StringIO(),
    )
    app.build()

    found = [w for w in build_warnings(app) if LOOSE_PART_WARNING in w]
    assert found == [
        f"<srcdir>/loose.rst:4: {LOOSE_PART_WARNING}"
    ]


def test_epub_reports_a_loose_part_once(make_app: Any, tmp_path: Path) -> None:
    """``epub`` reports a part outside every need once, as ``html`` does.

    The finding used to be made while a tree was resolved, and ``epub`` resolves
    the page holding the toctree for every document, so it was repeated.
    """
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(CONF, encoding="utf-8")
    (srcdir / "index.rst").write_text(
        "Index :np:`(x1) loose part`\n=====\n\nBody.\n", encoding="utf-8"
    )

    app = make_app(
        buildername="epub",
        srcdir=srcdir,
        builddir=tmp_path / "build" / "epub",
        freshenv=True,
        warning=io.StringIO(),
    )
    app.build()

    found = [w for w in build_warnings(app) if LOOSE_PART_WARNING in w]
    assert len(found) == 1, found
