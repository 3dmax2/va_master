from abc import ABCMeta, abstractmethod
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.httputil import url_concat
import tornado.gen
import tornado.ioloop
import json
import base64

class KeyNotFound(IOError):
    def __init__(self, doc_id):
        super(IOError, self).__init__('The DataStore doesn\'t have the ' + \
        'following doc_id: %s' % doc_id)
        self.doc_id = doc_id

class StoreError(Exception):
    def __init__(self, exc):
        """Parameters:
          exc - The internal exception that happened during Store transaction
        """
        super(Exception, self).__init__(repr(exc))
        self.exc = exc

class DataStore(object):
    """A DataStore is an abstract definition of an async key-value store that
    can contain objects targeted by id, and it should support CRUD operations.
    It is used for storing app metadata, scheduling data and configuration."""
    __metaclass__ =  ABCMeta
    KeyNotFound = KeyNotFound
    StoreError = StoreError

    @abstractmethod
    @tornado.gen.coroutine
    def check_connection(self): pass

    @abstractmethod
    @tornado.gen.coroutine
    def insert(self, doc_id, document): pass

    @abstractmethod
    @tornado.gen.coroutine
    def update(self, doc_id, document): pass

    @abstractmethod
    @tornado.gen.coroutine
    def get(self, doc_id): pass

    @abstractmethod
    @tornado.gen.coroutine
    def delete(self, doc_id): pass

class ConsulStore(DataStore):
    """A DataStore provided by Consul KV, that uses JSON for storage.
    Read more at: https://www.consul.io/docs/agent/http/kv.html"""
    def __init__(self, path='http://127.0.0.1:8500'):
        self.path = path
        self.client = AsyncHTTPClient()

    @tornado.gen.coroutine
    def check_connection(self):
        try:
            url = '%s/v1/status/leader' % self.path
            print ('Trying ', url)
            result = yield self.client.fetch(url)
        except:
            raise tornado.gen.Return(False)
        raise tornado.gen.Return(result.code == 200 and result.body != '""')

    @tornado.gen.coroutine
    def insert(self, doc_id, document):
        document_json = json.dumps(document)
        req = HTTPRequest('%s/v1/kv/%s' % (self.path, doc_id), method='PUT',
            body=document_json)
        try:
            yield self.client.fetch(req)
        except Exception as e:
            raise StoreError(e)

    @tornado.gen.coroutine
    def update(self, doc_id, document):
        try:
            yield self.insert(doc_id, document)
        except Exception as e:
            raise StoreError(e)

    @tornado.gen.coroutine
    def get_exec(self, doc_id, params = {}):
        is_ok = False
        resp = []
        try:
            url = '%s/v1/kv/%s' % (self.path, doc_id)
            if params: 
                url = url_concat(url, params)
            resp = yield self.client.fetch(url)
            resp = [x['Value'] for x in json.loads(resp.body)]
            resp = [base64.b64decode(x) for x in resp]

            resp = [json.loads(x) for x in resp]
#            if len(resp) == 1: resp = resp[0]
            is_ok = True
        except tornado.httpclient.HTTPError as e:
            if e.code == 404:
                raise KeyNotFound(doc_id)
            else:
                raise StoreError(e)
        except Exception as e:
            print ('Error processing : ', doc_id, ' and current resp is : ', resp)
            raise StoreError(e)
        if is_ok:
            raise tornado.gen.Return(resp)

    @tornado.gen.coroutine
    def get(self, doc_id):
        result = yield self.get_exec(doc_id)
        result = result[0]
        raise tornado.gen.Return(result)

    @tornado.gen.coroutine
    def get_recurse(self, doc_id):
        try:
            result = yield self.get_exec(doc_id, params = {"recurse" : True})
        except KeyNotFound: #If key is not found, we assume it's empty, so we default to an empty list. 
            result = []
        except: 
            print ('Error with keystore : ')
            import traceback
            traceback.print_exc()
        raise tornado.gen.Return(result)

    @tornado.gen.coroutine
    def delete(self, doc_id, params = None):
        try:
            url = '%s/v1/kv/%s' % (self.path, doc_id)
            if params: 
                url = url_concat(url, params)
            req = HTTPRequest(url, method='DELETE')
            yield self.client.fetch(req)
        except Exception as e:
            raise StoreError(e)
