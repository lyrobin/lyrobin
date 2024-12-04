"""Helper functions for testing the search engine."""

import functools
from search import client as search_client


def initialize_search_engine(func):

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        se = search_client.DocumentSearchEngine.create(api_key="xyz")
        se.drop_collection(collection="documents")
        se.drop_collection(collection="documents_v2")
        se.initialize_collections()
        func(*args, **kwargs)

    return wrapper
