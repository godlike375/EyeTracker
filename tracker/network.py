import multiprocessing
import queue
from abc import ABC, abstractmethod
from threading import Thread
from time import sleep

from tracker.abstractions import try_few_times, MutableVar


class Buffer(ABC):
    def __init__(self, stream: multiprocessing.Queue):
        self.stream = stream
        self.cache = queue.Queue()
        #self.thread = Thread(target=self.mainloop, daemon=True)
        self.result = MutableVar(None)
        #self.thread.start()

    @abstractmethod
    def mainloop(self):
        ...


class InputBuffer(Buffer):
    def mainloop(self):
        try_few_times(lambda : self.cache.put_nowait(self.stream.get_nowait()), times=1)

    def get_nowait(self):
        res = MutableVar()
        try_few_times(lambda: res.set(self.cache.get_nowait()))
        return res.value

    def get(self):
        return self.cache.get()


class OutputBuffer(Buffer):
    def mainloop(self):
        try_few_times(lambda: self.stream.put_nowait(self.cache.get_nowait()), times=1)

    def put_nowait(self, obj):
        try_few_times(lambda: self.cache.put_nowait(obj))

    def put(self, obj):
        return self.cache.put(obj)


class BufferPoller:
    def __init__(self, buffers: list[Buffer] = None):
        self.buffers = buffers or []
        self.pooler = Thread(target=self.poll)
        self.pooler.start()

    def poll(self):
        while True:
            for b in self.buffers:
                b.mainloop()
            if not self.buffers:
                sleep(0.1)
