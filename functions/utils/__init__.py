"""Utilities for interacting with Google Cloud Functions."""

# mypy: disable_error_code=return-value
import functools
import os
import re
from typing import TypeVar, Generic, Callable

import firebase_admin  # type: ignore
import google.auth  # type: ignore
import google.auth.transport.requests  # type: ignore
from firebase_functions.options import SupportedRegion
from google.auth import credentials
from google.auth.transport.requests import AuthorizedSession
from utils import testings

T = TypeVar("T")


def snake_to_camel(snake_str):
    """Converts a snake_case string to camelCase.

    Args:
        snake_str (str): The input string in snake_case format.

    Returns:
        str: The converted string in camelCase format.
    """
    components = snake_str.split("_")
    # Capitalize the first letter of each component except the first one
    # with the 'title' method and join them together.
    return components[0] + "".join(x.title() for x in components[1:])


def camel_to_snake(name: str) -> str:
    """
    Converts a camel case string to snake case.
    """
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def get_function_url(name: str, location: str = SupportedRegion.ASIA_EAST1) -> str:
    """Get the URL of a given v2 cloud function.

    Params:
        name: the function's name
        location: the function's location

    Returns: The URL of the function
    """
    if testings.is_using_emulators():
        host = os.environ.get("FUNCTIONS_EMULATOR_HOST")
        project = os.environ.get("GCLOUD_PROJECT", "")
        return f"http://{host}/{project}/{location}/{name}"
    credentials, project_id = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    authed_session = AuthorizedSession(credentials)
    url = (
        "https://cloudfunctions.googleapis.com/v2beta/"
        + f"projects/{project_id}/locations/{location}/functions/{name}"
    )
    response = authed_session.get(url)
    data = response.json()
    function_url = data["serviceConfig"]["uri"]
    return function_url


def refresh_credentials(func):
    """
    Refresh the credentials of the app.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        req = google.auth.transport.requests.Request()
        app: firebase_admin.App = firebase_admin.get_app()
        cred: credentials.Credentials = app.credential.get_credential()
        cred.refresh(req)
        return func(*args, **kwargs)

    return wrapper


class simple_cached_property(Generic[T]):
    """Decorator for class property to cache its value.
    Only not None value will be cached. The cached value will be kept in the instance.
    """

    def __init__(self, func: Callable[..., T]):
        self._func = func
        self._name: str | None = None

    def __set_name__(self, _, name: str):
        if self._name is None:
            self._name = name
        elif self._name != name:
            raise TypeError("Can't modify the property name after initialization")

    def __get__(self, instance, _) -> T:
        if instance is None:
            return self
        elif self._name is None:
            raise TypeError("Property not set")
        cached_value = getattr(instance, "_cached_" + self._name, None)
        if cached_value is not None:
            return cached_value
        value = self._func(instance)
        if value is not None:
            setattr(instance, "_cached_" + self._name, value)
        return value
