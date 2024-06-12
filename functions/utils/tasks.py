"""Cloud Run uilties"""

import requests

import utils
from utils import testings
from firebase_admin import functions
from firebase_functions import logger


class CloudRunQueue:
    """Cloud Run Queue"""

    def __init__(self, function_name: str):
        self._function_name = function_name
        self._queue = functions.task_queue(function_name)
        self._target = utils.get_function_url(function_name)
        self._option = functions.TaskOptions(
            dispatch_deadline_seconds=1800, uri=self._target
        )

    @classmethod
    def open(cls, function_name: str):
        """Open a queue"""
        return cls(function_name)

    def run(self, **kwargs):
        """Run the task"""
        data = {utils.snake_to_camel(k): v for k, v in kwargs.items()}
        if not testings.is_using_emulators():
            self._queue.enqueue({"data": data})
            return
        if not testings.is_background_trigger_enabled():
            logger.debug(f"{self._function_name} isn't forwared.")
            return
        res = requests.post(
            self._target,
            json={"data": data},
            headers={"content-type": "application/json"},
            timeout=120,
        )
        res.raise_for_status()
