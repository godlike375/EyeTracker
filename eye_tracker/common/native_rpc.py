import traceback
from multiprocessing import Process
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

        conn.send({'action': 'is_callable', 'obj_name': obj_name, 'attr': name})
        response = conn.recv()
        if 'error' in response:
            raise AttributeError(response['error'])
        is_callable = response['result']

        if is_callable:
            def method(*args, **kwargs):
                request = {
                    'action': 'call',
                    'obj_name': obj_name,
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
            conn.send({'action': 'getattr', 'obj_name': obj_name, 'attr': name})
            response = conn.recv()
            if 'error' in response:
                raise AttributeError(response['error'])
            return response['result']

    def __setattr__(self, name, value):
        conn = self._get_conn()
        obj_name = object.__getattribute__(self, '_object_name')
        request = {
            'action': 'setattr',
            'obj_name': obj_name,
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
            'obj_name': object.__getattribute__(self, '_object_name')
        }

    def __setstate__(self, state):
        object.__setattr__(self, '_address', state['address'])
        object.__setattr__(self, '_object_name', state['obj_name'])
        object.__setattr__(self, '_conn', None)


class RPCObjectServer:
    def __init__(self, address: tuple, use_thread: bool = False, start: bool = True):
        self._address = address
        self._use_thread = use_thread
        self._objects = {}  # Shared memory for threading mode
        self._executor = None
        if use_thread:
            self._parallel = Thread(target=self.serve, args=(self._address,), daemon=True)
            self._executor = ThreadPoolExecutor(max_workers=100)
        else:
            self._parallel = Process(target=self.serve, args=(self._address,))
        if start:
            self.start()

    def start(self):
        self._parallel.start()

    def terminate_and_join(self):
        if isinstance(self._parallel, Process):
            self._parallel.terminate()
            self._parallel.join()
        else:
            self._executor.shutdown(wait=False)

    def add_object(self, name: str, obj: object) -> RPCObjectProxy:
        if self._use_thread:
            self._objects[name] = obj
        else:
            conn = Client(self._address)
            conn.send({'action': 'add_object', 'name': name, 'object': obj})
            response = conn.recv()
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
            conn = Client(self._address)
            conn.send(request)
            response = conn.recv()
            if 'error' in response:
                raise AttributeError(response['error'])
        return self.get_proxy(name)

    def get_proxy(self, name: str) -> RPCObjectProxy:
        return RPCObjectProxy(self._address, name)

    def __getattr__(self, name):
        if name.startswith('_'):
            return super().__getattribute__(name)
        if self._use_thread:
            return self._objects[name]
        return self.get_proxy(name)

    def __setattr__(self, name, obj):
        if name.startswith('_'):
            super().__setattr__(name, obj)
        else:
            self.add_object(name, obj)

    def serve(self, address):
        listener = Listener(address, family='AF_INET')

        def handle_connection(conn: Connection, objects_dict: dict):
            while True:
                try:
                    request = conn.recv()
                    #print(request)
                    response = RPCObjectServer.handle_request(request, objects_dict)
                    conn.send(response)
                except EOFError:
                    break
            conn.close()

        if not self._use_thread:
            self._executor = ThreadPoolExecutor(max_workers=100)
        with self._executor as executor:
            while True:
                conn = listener.accept()
                executor.submit(handle_connection, conn, self._objects)

    @staticmethod
    def handle_request(request, objects):
        cmd = request.get('action')
        try:
            match cmd:
                case 'call':
                    obj = objects[request['obj_name']]
                    method = getattr(obj, request['method'])
                    result = method(*request['args'], **request['kwargs'])
                    return {'result': result}
                case 'getattr':
                    obj = objects[request['obj_name']]
                    return {'result': getattr(obj, request['attr'])}

                case 'setattr':
                    obj = objects[request['obj_name']]
                    setattr(obj, request['attr'], request['value'])
                    return {'result': request['value']}
                case 'is_callable':
                    obj = objects[request['obj_name']]
                    attr = getattr(obj, request['attr'])
                    return {'result': callable(attr)}
                case 'add_object':
                    objects[request['name']] = request['object']
                    return {'result': None}
                case 'instantiate':
                    cls = request['class']
                    args = request['args']
                    kwargs = request['kwargs']
                    objects[request['name']] = cls(*args, **kwargs)
                    return {'result': None}
                case _:
                    return {'error': 'Unknown action: ' + str(cmd)}
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
        self.text = 'test'


class A:
    def __init__(self, b):
        self.b = b


if __name__ == '__main__':

    server = RPCObjectServer(('localhost', 6000), use_thread=True)
    server.a = A(B())

    server2 = RPCObjectServer(('localhost', 6001), use_thread=True)
    server2.b = server.a.b
    server2.b.text = 'modified'
    print(server.a.b.text)

    server.terminate_and_join()
    server2.terminate_and_join()