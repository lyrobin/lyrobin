from firebase_admin import firestore  # type: ignore
from utils import tasks, testings
from wiki import models


@testings.skip_when_no_network
@testings.require_firestore_emulator
def test_update_directors_wiki():
    q = tasks.CloudRunQueue.open("updateOrgDirectorsWiki")
    q.run(org="國立故宮博物院")

    db = firestore.client()
    docs = (
        db.collection(models.DIRECTORS_COLLECTION)
        .where("organization", "==", "國立故宮博物院")
        .get()
    )
    assert len(docs) == 1
