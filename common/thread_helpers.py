from sys import exit
from threading import (
    Thread, Event, current_thread
)
from time import sleep


# https://stackoverflow.com/questions/323972/is-there-any-way-to-kill-a-thread
class StoppableThread(Thread):
    # Thread class with a stop() method

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = Event()

    def stop(self):
        self._stop_event.set()

    def is_stopped(self):
        return self._stop_event.is_set()


# https://gist.github.com/awesomebytes/0483e65e0884f05fb95e314c4f2b3db8
def threaded(fn):
    # To use as decorator to make a function call threaded
    def wrapper(*args, **kwargs):
        thread = StoppableThread(target=fn, args=args, kwargs=kwargs)
        return thread

    return wrapper


@threaded
def thread_loop_runner(func, interval: float = 0.05):
    while True:
        sleep(interval)
        if current_thread().is_stopped():
            exit(0)
        func()


class ThreadLoopable:
    def __init__(self, loop_func, interval: float, run_immediately: bool = True):
        if run_immediately:
            self.start_thread(loop_func, interval)

    def start_thread(self, loop_func, interval):
        self._thread_loop = thread_loop_runner(loop_func, interval)
        self._thread_loop.start()

    def stop_thread(self):
        self._thread_loop.stop()
