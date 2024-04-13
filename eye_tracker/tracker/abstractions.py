import pickle


class Packable:
    def pack(self) -> bytes:
        return pickle.dumps(self)

    @classmethod
    def unpack(cls, bytes) -> 'Packable':
        return pickle.loads(bytes)


class ID(int):...
