import multiprocessing as mp

class ObjectStore:
    def __init__(self):
        self.objects = {}
        self._next_id = 1

    def register(self, obj):
        obj_id = self._next_id
        self.objects[obj_id] = obj
        self._next_id += 1
        return obj_id

    def get(self, obj_id):
        return self.objects[obj_id]


def server_loop(conn):
    store = ObjectStore()

    # пример объектов
    class C:
        def __init__(self):
            self.value = 0

    class B:
        def __init__(self):
            self.c = C()

    class A:
        def __init__(self):
            self.b = B()

        def do_something(self, x):
            return x * 2

    root = A()
    root_id = store.register(root)

    conn.send({"root_id": root_id})

    while True:
        msg = conn.recv()
        if msg == "shutdown":
            break

        obj = store.get(msg["obj_id"])

        if msg["op"] == "get":
            val = getattr(obj, msg["name"])
            if isinstance(val, (int, float, str, bool, type(None))):
                conn.send({"type": "value", "value": val})
            else:
                obj_id = store.register(val)
                conn.send({"type": "ref", "obj_id": obj_id})

        elif msg["op"] == "set":
            setattr(obj, msg["name"], msg["value"])
            conn.send({"type": "ok"})

        elif msg["op"] == "call":
            result = getattr(obj, msg["name"])(*msg["args"], **msg["kwargs"])
            if isinstance(result, (int, float, str, bool, type(None))):
                conn.send({"type": "value", "value": result})
            else:
                obj_id = store.register(result)
                conn.send({"type": "ref", "obj_id": obj_id})


class RemoteProxy:
    def __init__(self, conn, obj_id):
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_id", obj_id)

    def __getattr__(self, name):
        self._conn.send({
            "op": "get",
            "obj_id": self._id,
            "name": name
        })
        resp = self._conn.recv()

        if resp["type"] == "value":
            return resp["value"]
        return RemoteProxy(self._conn, resp["obj_id"])

    def __setattr__(self, name, value):
        self._conn.send({
            "op": "set",
            "obj_id": self._id,
            "name": name,
            "value": value
        })
        self._conn.recv()

    def __call__(self, *args, **kwargs):
        self._conn.send({
            "op": "call",
            "obj_id": self._id,
            "name": "__call__",
            "args": args,
            "kwargs": kwargs
        })
        resp = self._conn.recv()
        return resp["value"]


if __name__ == "__main__":
    parent, child = mp.Pipe()

    p = mp.Process(target=server_loop, args=(child,))
    p.start()

    root_id = parent.recv()["root_id"]
    a = RemoteProxy(parent, root_id)

    print(a.b.c.value)     # 0
    a.b.c.value = 123
    print(a.b.c.value)     # 123
    print(a.do_something(5))  # 10

    parent.send("shutdown")
    p.join()
