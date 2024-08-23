import io

from firebase_admin import firestore  # type: ignore
from firebase_functions import logger, tasks_fn, https_fn
from firebase_functions.options import (
    MemoryOption,
    RateLimits,
    RetryConfig,
    SupportedRegion,
)
from wiki import models, parsers
from utils import tasks
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel  # type: ignore
from params import EMBEDDING_MODEL


@tasks_fn.on_task_dispatched(
    retry_config=RetryConfig(max_attempts=3, max_backoff_seconds=300),
    rate_limits=RateLimits(max_concurrent_dispatches=100),
    memory=MemoryOption.MB_512,
    max_instances=5,
    concurrency=20,
    region=SupportedRegion.ASIA_EAST1,
)
def updateOrgDirectorsWiki(request: tasks_fn.CallableRequest):
    try:
        org = request.data["org"]
        r = parsers.OrganizationReader(org)
        tables = [t.iloc[-10:] for t in r.directors_tables]
        s = io.StringIO()
        for table in tables:
            s.write(table.to_markdown())
            s.write("\n\n")
        model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL.value)
        embeddings = model.get_embeddings(
            [TextEmbeddingInput(org, "RETRIEVAL_DOCUMENT")],
            output_dimensionality=models.EMBEDDING_SIZE,
        )
        m = models.DirectorsDocument(
            organization=org, markdown=s.getvalue(), embedding=embeddings[0].values
        )
        db = firestore.client()
        db.collection(models.DIRECTORS_COLLECTION).document(m.document_id()).set(
            m.to_dict(), merge=True
        )

    except Exception as e:
        logger.error(f"Fail to update org directors wiki, {e}")
        raise RuntimeError("Fail to update org directors wiki") from e


@https_fn.on_request(region=SupportedRegion.ASIA_EAST1, memory=MemoryOption.MB_512)
def update_directors_wiki(_: https_fn.Request) -> https_fn.Response:
    try:
        _update_directors_wiki()
    except Exception as e:
        logger.error(f"Fail to update directors wiki, {e}")
        raise RuntimeError("Fail to update directors wiki") from e
    return https_fn.Response("OK")


def _update_directors_wiki():
    q = tasks.CloudRunQueue.open("updateOrgDirectorsWiki")
    for org in parsers.get_organizations():
        q.run(org=org)
