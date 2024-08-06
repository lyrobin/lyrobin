import io
from ai import context

import pathlib


def test_attach_legislators_background():
    buf = io.StringIO()
    context.attach_legislators_background(buf, [11])
    content = buf.getvalue()

    assert "黃國昌" in content
