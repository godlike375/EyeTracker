from common.thread_helpers import ThreadLoopable, MutableValue
from time import sleep


def test_thread_loopable():
    thread_loop_interval = MutableValue(0.000001)
    thread_loop_run_time = 0.45

    class Loopable(ThreadLoopable):
        def __init__(self):
            self.counter = 0
            super().__init__(self.loop, interval=thread_loop_interval)

        def loop(self):
            self.counter += 1

    loopable = Loopable()
    thread_loop_interval.value = 0.15
    sleep(thread_loop_run_time)
    loopable.stop_thread()
    assert loopable.counter < 4
