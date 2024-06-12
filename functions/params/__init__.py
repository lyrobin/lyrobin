from firebase_functions.params import IntParam, StringParam

DEFAULT_TIMEOUT_SEC = IntParam(
    name="DEFAULT_TIMEOUT_SEC", default=60, description="Default timeout in seconds"
)

CLOUD_DOC2TXT_API = StringParam(
    name="CLOUD_DOC2TXT_API",
    default="http://127.0.0.1:5002",
    description="Cloud Doc2Txt API",
)

STORAGE_BUCKET = StringParam(
    name="STORAGE_BUCKET",
    default="taiwan-legislative-search.appspot.com",
    description="Storage Bucket",
)
