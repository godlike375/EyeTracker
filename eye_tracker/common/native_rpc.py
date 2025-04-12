import traceback
from multiprocessing import Process, Pipe, freeze_support
from multiprocessing.connection import Connection


class RPCObjectProxy:
    def __init__(self, conn: Connection):
        object.__setattr__(self, '_conn', conn)

    def __getattr__(self, name):
        conn = object.__getattribute__(self, '_conn')

        # Проверяем, является ли атрибут вызываемым
        conn.send({'action': 'is_callable', 'attr': name})
        response = conn.recv()
        if 'error' in response:
            raise AttributeError(response['error'])
        is_callable = response['result']

        if is_callable:
            def method(*args, **kwargs):
                request = {
                    'action': 'call',
                    'method': name,
                    'args': args,
                    'kwargs': kwargs
                }
                conn.send(request)
                response = conn.recv()
                if 'error' in response:
                    error = response['error']
                    raise Exception(f"{error['type']}: {error['message']}\n{error['traceback']}")
                return response['result']

            return method
        else:
            conn.send({'action': 'getattr', 'attr': name})
            response = conn.recv()
            if 'error' in response:
                raise AttributeError(response['error'])
            return response['result']

    def __setattr__(self, name, value):
        conn = object.__getattribute__(self, '_conn')
        request = {
            'action': 'setattr',
            'attr': name,
            'value': value
        }
        conn.send(request)
        response = conn.recv()
        if 'error' in response:
            error = response['error']
            raise AttributeError(f"Setattr failed: {error['message']}")


class RPCObjectServer:
    def __init__(self, obj: object, start: bool = True):
        self.obj = obj
        self.parent_conn, self.child_conn = Pipe()
        self.process = Process(target=self.serve)
        if start:
            self.start()

    def start(self):
        self.process.start()

    def terminate_and_join(self):
        self.process.terminate()
        self.process.join()

    def get_proxy(self):
        return RPCObjectProxy(self.parent_conn)

    def serve(self):
        conn = self.child_conn
        while True:
            try:
                request = conn.recv()
                response = self.handle_request(request)
                conn.send(response)
            except EOFError:
                break

    def handle_request(self, request):
        action = request["action"]
        obj = self.obj

        try:
            if action == "call":
                method = getattr(obj, request["method"])
                result = method(*request["args"], **request["kwargs"])
                return {"result": result}
            elif action == "getattr":
                return {"result": getattr(obj, request["attr"])}
            elif action == "setattr":
                setattr(obj, request["attr"], request["value"])
                return {"result": request["value"]}
            elif action == "is_callable":
                attr = getattr(obj, request["attr"])
                return {"result": callable(attr)}
            else:
                return {"error": "Unknown action"}
        except Exception as e:
            return {
                "error": {
                    "type": e.__class__.__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }
            }
