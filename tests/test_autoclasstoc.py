# Integration tests, where the inputs are RST files and the outputs are HTML 
# files.

import pytest, parametrize_from_file as pff, re_assert
import lxml.html
import sys

from pathlib import Path
from contextlib import contextmanager

@pff.parametrize(
        schema=pff.defaults(expected={}, forbidden={}, stderr=[]),
        indirect=['tmp_files'],
)
def test_autoclasstoc(tmp_files, expected, forbidden, stderr, monkeypatch, capsys):
    # Fill in missing files:

    conf_py = tmp_files / 'conf.py'
    if not conf_py.exists():
        conf_py.write_text("""\
extensions = [
        'autoclasstoc',
        'sphinx.ext.autosummary',
]
""")

    # Run sphinx:

    monkeypatch.syspath_prepend(tmp_files)

    with cleanup_imports():
        from sphinx.cmd.build import build_main
        build_main([
                '-b', 'html',
                str(tmp_files),
                str(tmp_files / 'build'),
        ])

    # Check the error messages:
    
    cap = capsys.readouterr()

    for pattern in stderr:
        re_assert.Matches(pattern).assert_matches(cap.err)

    # Check the HTML results:

    html_paths = [*expected.keys(), *forbidden.keys()]

    for html_path in html_paths:
        html_str = (tmp_files / 'build' / html_path).read_text()
        html = lxml.html.fromstring(html_str)

        for xpath, pattern in expected.get(html_path, {}).items():
            hits = html.xpath(xpath)

            if not hits:
                raise AssertionError(f"xpath query didn't match any elements in {html_path!r}: {xpath}")

            for hit in hits:
                if isinstance(hit, lxml.html.HtmlElement):
                    hit = hit.text_content()
                re_assert.Matches(pattern).assert_matches(hit)

        for xpath in forbidden.get(html_path, []):
            if html.xpath(xpath):
                raise AssertionError(f"forbidden xpath query matched {html_path!r}: {xpath}")

@contextmanager
def cleanup_imports():
    """
    Unimport any modules/packages that were imported within the `with` block.

    The reason for doing this is to keep the test cases independent from each 
    other.  Python caches imported modules/packages by default, so without 
    this, imports made by one test case would persist into the next.

    There are really two specific modules/packages that cause problems:

        `mock_project`:
            Most of the test cases include a module with this name that defines 
            the python objects to document in that test.  It's easy to see how 
            caching this module between test cases could lead to problems.  
            This could be avoided by using a different module name for each 
            test case, but that's too much of a burden on the test author.

        `sphinx`:
            I don't exactly understand how, but there is some amount of global 
            state that is stored somewhere in the this package.  I think it has 
            something to do with the way attribute docstrings are parsed, 
            because (i) the tests that involve attributes fail when sphinx 
            isn't un-imported between test cases and (ii) attributes don't 
            really have docstrings, so sphinx has to do some magic to make it 
            seem like they do.  In any case, un-importing this module solves 
            the problem.
    """
    try:
        whitelist = set(sys.modules.keys())
        yield
    finally:
        for key in list(sys.modules):
            if key not in whitelist:
                del sys.modules[key]

