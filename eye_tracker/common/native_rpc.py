import traceback
from multiprocessing import Process, Pipe, freeze_support
from multiprocessing.connection import Connection
from threading import Thread


class RPCObjectProxy:
    def __init__(self, conn: Connection, object_name: str):
        object.__setattr__(self, '_conn', conn)
        object.__setattr__(self, '_name', object_name)

    def __getattr__(self, name):
        conn = object.__getattribute__(self, '_conn')
        obj_name = object.__getattribute__(self, '_name')

        # Check if attribute is callable on the target object
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
        conn = object.__getattribute__(self, '_conn')
        obj_name = object.__getattribute__(self, '_name')
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


class RPCObjectServer:
    def __init__(self, start: bool = True, use_thread: bool = False):
        self._parent_conn, self._child_conn = Pipe()
        self._use_thread = use_thread
        self._objects = {}
        self._parallel = Thread(target=self.serve) if use_thread else Process(target=self.serve)
        if start:
            self.start()

    def start(self):
        freeze_support()
        self._parallel.start()

    def terminate_and_join(self):
        if isinstance(self._parallel, Process):
            self._parallel.terminate()
        self._parallel.join()

    def add_object(self, name: str, obj: object) -> RPCObjectProxy:
        """
        Add an existing object to the RPC server under the given name.
        If using threads, share by reference; if using processes, send via pipe (serialized).
        """
        if self._use_thread:
            # In threading mode, objects live in shared memory
            self._objects[name] = obj
        else:
            # Send object to child process to add
            self._parent_conn.send({'action': 'add_object', 'name': name, 'object': obj})
            response = self._parent_conn.recv()
            if 'error' in response:
                raise Exception(f"Error adding object: {response['error']}")
        return self.get_proxy(name)

    def instantiate_object_from_class(self, name: str, cls: type, *args, **kwargs) -> RPCObjectProxy:
        """
        Instantiate a new object of given class inside the server process/thread.
        """
        request = {
                'action': 'instantiate',
                'name': name,
                'class': cls,
                'args': args,
                'kwargs': kwargs
            }
        self._parent_conn.send(request)
        response = self._parent_conn.recv()
        if 'error' in response:
            raise AttributeError(response['error'])
        return self.get_proxy(name)

    def get_proxy(self, name: str) -> RPCObjectProxy:
        if name not in self._objects and not self._use_thread:
            # In process mode, child may know the object without parent tracking
            pass
        return RPCObjectProxy(self._parent_conn, name)

    def __getattr__(self, name):
        if name.startswith('_'):
            return super().__getattribute__(name)
        return self.get_proxy(name)

    def __setattr__(self, name, object: object):
        if name.startswith('_'):
            super().__setattr__(name, object)
        else:
            self.add_object(name, object)


    def serve(self):
        while True:
            try:
                request = self._child_conn.recv()
                response = self.handle_request(request)
                self._child_conn.send(response)
            except EOFError:
                break

    def handle_request(self, request):
        action = request.get('action')
        try:
            if action == 'call':
                obj = self._objects[request['object_name']]
                method = getattr(obj, request['method'])
                result = method(*request['args'], **request['kwargs'])
                return {'result': result}

            elif action == 'getattr':
                obj = self._objects[request['object_name']]
                return {'result': getattr(obj, request['attr'])}

            elif action == 'setattr':
                obj = self._objects[request['object_name']]
                setattr(obj, request['attr'], request['value'])
                return {'result': request['value']}

            elif action == 'is_callable':
                obj = self._objects[request['object_name']]
                attr = getattr(obj, request['attr'])
                return {'result': callable(attr)}

            elif action == 'add_object':
                # add_object only handled in child for process mode
                name = request['name']
                self._objects[name] = request['object']
                return {'result': None}

            elif action == 'instantiate':
                name = request['name']
                cls = request['class']
                args = request['args']
                kwargs = request['kwargs']
                self._objects[name] = cls(*args, **kwargs)
                return {'result': None}

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
