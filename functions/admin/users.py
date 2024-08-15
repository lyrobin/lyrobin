"""User management module."""

import dataclasses

from admin import models
from firebase_admin import firestore  # type: ignore
from firebase_functions import https_fn, identity_fn
from firebase_functions.options import SupportedRegion, MemoryOption
from utils import testings

AUTH_PROVIDER_GOOGLE = "google.com"


@identity_fn.before_user_created(
    region=SupportedRegion.ASIA_EAST1,
    id_token=True,
    access_token=True,
    refresh_token=True,
    memory=MemoryOption.MB_512,
)
def handle_user_sign_up(
    event: identity_fn.AuthBlockingEvent,
) -> identity_fn.BeforeCreateResponse | None:
    if testings.is_using_emulators():
        return None
    cred = event.credential
    if not cred or cred.provider_id != AUTH_PROVIDER_GOOGLE:
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.PERMISSION_DENIED,
            message="Invalid auth provider.",
        )
    user = event.data
    m = models.User(
        user.uid,
        google_access_token=cred.access_token,
        google_refresh_token=cred.refresh_token,
        google_expiration_time=cred.expiration_time,
    )
    db = firestore.client()
    db.collection(models.USER_COLLECTION).document(user.uid).set(
        dataclasses.asdict(m), merge=True
    )
    return None
