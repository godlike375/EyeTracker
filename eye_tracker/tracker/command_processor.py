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
    def __init__(self):
        self.queue = CommandQueue()

    def __len__(self):
        return len(self.queue._queue)

    async def exec_queued_commands(self):
        for command in self.queue:
            await command()

    def exec_latest_command(self):
        command = self.queue.pop_command()
        if command is not None:
            command()
            return True
        return False

    def queue_command(self, command):
        self.queue.add_command(command)
