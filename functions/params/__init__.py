from firebase_functions.params import IntParam

DEFAULT_TIMEOUT_SEC = IntParam(
    name="DEFAULT_TIMEOUT_SEC", default=60, description="Default timeout in seconds"
)
