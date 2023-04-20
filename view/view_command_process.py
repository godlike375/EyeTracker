from collections import deque

class CommandQueue:
    def __init__(self):
        self._queue = deque()

    def add_command(self, command):
        self._queue.append(command)

    def pop_command(self):
        if len(self._queue):
            return self._queue.popleft()
        return None

    def __next__(self):
        command = self.pop_command()
        if not command:
            raise StopIteration
        return command

    def __iter__(self):
        return self

class CommandExecutor:
    def __init__(self, view):
        self._view = view
        self._queue = CommandQueue()

    def exec_queued_commands(self):
        for command in self._queue:
            command()

    def queue_command(self, command):
        self._queue.add_command(command)
