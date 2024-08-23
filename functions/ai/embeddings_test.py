from ai import embeddings
from firebase_admin import firestore  # type: ignore
from legislature import models
from utils import testings


@testings.require_firestore_emulator
@testings.skip_when_no_network
def test_get_embeddings_from_text():
    db = firestore.client()

    ref = db.document("meetings/2024021799/files/3e9c608ef0dc3fef9ed225144a738980")
    m = models.MeetingFile.from_dict(ref.get().to_dict())

    vectors = embeddings.get_embeddings_from_text(m.full_text)

    assert len(vectors) >= 10
