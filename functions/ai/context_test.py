import io

from firebase_admin import firestore
from ai import context, embeddings
from google.cloud.firestore_v1.vector import Vector
from utils import testings
from legislature import models


def test_attach_legislators_background():
    db = firestore.client()
    ref = db.collection(models.MEMBER_COLLECT).document()
    ref.set(models.Legislator(name="黃國昌", terms=["11"]).asdict())
    buf = io.StringIO()
    context.attach_legislators_background(buf, [11])
    content = buf.getvalue()

    assert "黃國昌" in content


@testings.require_firestore_emulator
@testings.skip_when_no_network
def test_attach_directors_background():
    vectors = [Vector(e) for e in embeddings.get_embeddings_from_text("衛福部")]

    buf = io.StringIO()
    context.attach_directors_background(buf, vectors)

    assert "邱泰源" in buf.getvalue()
