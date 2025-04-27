import traceback
from multiprocessing import Process, Pipe
from multiprocessing.connection import Listener, Client, Connection
from threading import Thread
from concurrent.futures import ThreadPoolExecutor

class RPCObjectProxy:
    def __init__(self, address: tuple, object_name: str):
        object.__setattr__(self, '_address', address)
        object.__setattr__(self, '_object_name', object_name)
        object.__setattr__(self, '_conn', None)

    def _get_conn(self):
        if object.__getattribute__(self, '_conn') is None:
            conn = Client(object.__getattribute__(self, '_address'))
            object.__setattr__(self, '_conn', conn)
        return object.__getattribute__(self, '_conn')

    def __getattr__(self, name):
        conn = self._get_conn()
        obj_name = object.__getattribute__(self, '_object_name')

        conn.send({'action': 'is_callable', 'object_name': obj_name, 'attr': name})
        response = conn.recv()
        if 'error' in response:
            raise AttributeError(response['error'])
        is_callable = response['result']

        if is_callable:
            def method(*args, **kwargs):
                request = {
                    'action': 'call',
                    'object_name': obj_name,
                    'method': name,
                    'args': args,
                    'kwargs': kwargs
                }
                conn.send(request)
                response = conn.recv()
                if 'error' in response:
                    err = response['error']
                    raise Exception(f"{err['type']}: {err['message']}\n{err['traceback']}")
                return response['result']
            return method
        else:
            conn.send({'action': 'getattr', 'object_name': obj_name, 'attr': name})
            response = conn.recv()
            if 'error' in response:
                raise AttributeError(response['error'])
            return response['result']

    def __setattr__(self, name, value):
        conn = self._get_conn()
        obj_name = object.__getattribute__(self, '_object_name')
        request = {
            'action': 'setattr',
            'object_name': obj_name,
            'attr': name,
            'value': value
        }
        conn.send(request)
        response = conn.recv()
        if 'error' in response:
            err = response['error']
            raise AttributeError(f"Setattr failed: {err['message']}")

    def __getstate__(self):
        return {
            'address': object.__getattribute__(self, '_address'),
            'object_name': object.__getattribute__(self, '_object_name')
        }

    def __setstate__(self, state):
        object.__setattr__(self, '_address', state['address'])
        object.__setattr__(self, '_object_name', state['object_name'])
        object.__setattr__(self, '_conn', None)

class RPCObjectServer:
    def __init__(self, address: tuple, use_thread: bool = False, start: bool = True):
        self._address = address
        self._use_thread = use_thread
        self._control_parent_conn, self._control_child_conn = Pipe()
        self._objects = {}  # Shared memory for threading mode
        if use_thread:
            self._parallel = Thread(target=self.serve_threading, args=(self._address, self._control_child_conn))
        else:
            self._parallel = Process(target=self.serve_processing, args=(self._address, self._control_child_conn))
        if start:
            self.start()

    def start(self):
        self._parallel.start()

    def terminate_and_join(self):
        if isinstance(self._parallel, Process):
            self._parallel.terminate()
        self._parallel.join()

    def add_object(self, name: str, obj: object) -> RPCObjectProxy:
        if self._use_thread:
            self._objects[name] = obj
        else:
            self._control_parent_conn.send({'action': 'add_object', 'name': name, 'object': obj})
            response = self._control_parent_conn.recv()
            if 'error' in response:
                raise Exception(f"Error adding object: {response['error']}")
        return self.get_proxy(name)

    def instantiate_object_from_class(self, name: str, cls: type, *args, **kwargs) -> RPCObjectProxy:
        if self._use_thread:
            self._objects[name] = cls(*args, **kwargs)
        else:
            request = {
                'action': 'instantiate',
                'name': name,
                'class': cls,
                'args': args,
                'kwargs': kwargs
            }
            self._control_parent_conn.send(request)
            response = self._control_parent_conn.recv()
            if 'error' in response:
                raise AttributeError(response['error'])
        return self.get_proxy(name)

    def get_proxy(self, name: str) -> RPCObjectProxy:
        return RPCObjectProxy(self._address, name)

    def __getattr__(self, name):
        if name.startswith('_'):
            return super().__getattribute__(name)
        return self.get_proxy(name)

    def __setattr__(self, name, obj):
        if name.startswith('_'):
            super().__setattr__(name, obj)
        else:
            self.add_object(name, obj)

    def serve_processing(self, address, control_conn: Connection):
        listener = Listener(address)

        def handle_connection(conn: Connection, objects_dict: dict):
            while True:
                try:
                    request = conn.recv()
                    response = RPCObjectServer.handle_request(request, objects_dict)
                    conn.send(response)
                except EOFError:
                    break
            conn.close()

        with ThreadPoolExecutor(max_workers=10) as executor:
            while True:
                if control_conn.poll():
                    cmd = control_conn.recv()
                    print(cmd)
                    if cmd['action'] == 'add_object':
                        self._objects[cmd['name']] = cmd['object']
                        control_conn.send({'result': None})
                    elif cmd['action'] == 'instantiate':
                        cls = cmd['class']
                        args = cmd['args']
                        kwargs = cmd['kwargs']
                        self._objects[cmd['name']] = cls(*args, **kwargs)
                        control_conn.send({'result': None})

                conn = listener.accept()
                executor.submit(handle_connection, conn, self._objects)

    def serve_threading(self, address, control_conn: Connection):
        listener = Listener(address)

        def handle_connection(conn: Connection, objects_dict: dict):
            while True:
                try:
                    request = conn.recv()
                    response = RPCObjectServer.handle_request(request, objects_dict)
                    conn.send(response)
                except EOFError:
                    break
            conn.close()

        with ThreadPoolExecutor(max_workers=10) as executor:
            while True:
                if control_conn.poll():
                    cmd = control_conn.recv()
                    if cmd['action'] == 'add_object':
                        self._objects[cmd['name']] = cmd['object']
                        control_conn.send({'result': None})
                    elif cmd['action'] == 'instantiate':
                        cls = cmd['class']
                        args = cmd['args']
                        kwargs = cmd['kwargs']
                        self._objects[cmd['name']] = cls(*args, **kwargs)
                        control_conn.send({'result': None})

                conn = listener.accept()
                executor.submit(handle_connection, conn, self._objects)

    @staticmethod
    def handle_request(request, objects):
        action = request.get('action')
        try:
            if action == 'call':
                obj = objects[request['object_name']]
                method = getattr(obj, request['method'])
                result = method(*request['args'], **request['kwargs'])
                return {'result': result}

            elif action == 'getattr':
                obj = objects[request['object_name']]
                return {'result': getattr(obj, request['attr'])}

            elif action == 'setattr':
                obj = objects[request['object_name']]
                setattr(obj, request['attr'], request['value'])
                return {'result': request['value']}

            elif action == 'is_callable':
                obj = objects[request['object_name']]
                attr = getattr(obj, request['attr'])
                return {'result': callable(attr)}

            else:
                return {'error': 'Unknown action: ' + str(action)}
        except Exception as e:
            return {
                'error': {
                    'type': e.__class__.__name__,
                    'message': str(e),
                    'traceback': traceback.format_exc()
                }
            }

class B:
    def __init__(self):
        self.a = None

class A:
    def __init__(self, b):
        self.b = b

if __name__ == '__main__':
    server = RPCObjectServer(('localhost', 6000), use_thread=False)
    server.a = A(B())

    server2 = RPCObjectServer(('localhost', 6001), use_thread=False)
    server2.b = server.a
    server2.b.a = server.a

    server.terminate_and_join()
    server2.terminate_and_join()