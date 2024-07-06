"""Cloud Run uilties"""

import requests  # type: ignore

import utils
from utils import testings
from firebase_admin import functions  # type: ignore
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

    @utils.refresh_credentials
    def run(self, **kwargs):
        """Run the task"""
        data = {utils.snake_to_camel(k): v for k, v in kwargs.items()}
        if not testings.is_using_emulators():
            task_id = self._queue.enqueue({"data": data}, self._option)
            logger.debug(f"task_id({self._target}): {task_id}")
            return
        if not testings.is_background_trigger_enabled():
            logger.debug(f"{self._function_name} isn't forwarded.")
            return
        res = requests.post(
            self._target,
            json={"data": data},
            headers={"content-type": "application/json"},
            timeout=120,
        )
        res.raise_for_status()
