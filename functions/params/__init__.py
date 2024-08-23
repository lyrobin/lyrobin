from firebase_functions.params import IntParam, StringParam, SecretParam

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

TYPESENSE_HOST = StringParam(
    name="TYPESENSE_HOST",
    default="127.0.0.1",
    description="Typesense Host",
)

TYPESENSE_PORT = StringParam(
    name="TYPESENSE_PORT",
    default="8108",
    description="Typesense Port",
)

TYPESENSE_PROTOCOL = StringParam(
    name="TYPESENSE_PROTOCOL",
    default="http",
    description="Typesense Protocol",
)

TYPESENSE_API_KEY = SecretParam(
    name="TYPESENSE_API_KEY",
    description="Typesense API Key",
)

EMBEDDING_MODEL = StringParam(
    name="EMBEDDING_MODEL",
    default="text-multilingual-embedding-002",
    description="Embedding Model",
)

EMBEDDING_SIZE = IntParam(
    name="EMBEDDING_SIZE",
    default=768,
    description="Embedding Size",
)
