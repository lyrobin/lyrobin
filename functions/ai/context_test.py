import io
from ai import context

from utils import testings


def test_attach_legislators_background():
    buf = io.StringIO()
    context.attach_legislators_background(buf, [11])
    content = buf.getvalue()

    assert "黃國昌" in content


@testings.require_firestore_emulator
@testings.skip_when_no_network
def test_attach_directors_background():
    buf = io.StringIO()
    context.attach_directors_background(buf, "衛福部")

    assert "邱泰源" in buf.getvalue()
