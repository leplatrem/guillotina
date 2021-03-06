from guillotina.db.cache.base import BaseCache
from guillotina.db.transaction import Transaction
from guillotina.tests import mocks
from guillotina.tests.utils import create_content


class MemoryCache(BaseCache):

    def __init__(self, storage, transaction):
        super().__init__(storage, transaction)
        self._cache = {}
        self._actions = []

    async def get(self, **kwargs):
        key = self.get_key(**kwargs)
        if key in self._cache:
            self._actions.append({
                'action': 'loaded',
                'key': key
            })
            return self._cache[key]

    async def set(self, value, **kwargs):
        key = self.get_key(**kwargs)
        self._actions.append({
            'action': 'stored',
            'key': key
        })
        self._cache[key] = value

    async def clear(self):
        self._cache.clear()
        self._actions = []

    async def delete(self, key):
        self._actions.append({
            'action': 'delete',
            'key': key
        })
        if key in self._cache:
            del self._cache[key]

    async def delete_all(self, keys):
        for key in keys:
            await self.delete(keys)


async def test_cache_object(dummy_guillotina):
    tm = mocks.MockTransactionManager()
    storage = tm._storage
    txn = Transaction(tm)
    cache = MemoryCache(storage, txn)
    txn._cache = cache
    ob = create_content()
    storage.store(ob)
    loaded = await txn.get(ob._p_oid)
    assert id(loaded) != id(ob)
    assert loaded._p_oid == ob._p_oid
    assert cache._actions[0]['action'] == 'stored'

    # and load from cache
    await txn.get(ob._p_oid)
    assert cache._actions[-1]['action'] == 'loaded'


async def test_cache_object_from_child(dummy_guillotina):
    tm = mocks.MockTransactionManager()
    storage = tm._storage
    txn = Transaction(tm)
    cache = MemoryCache(storage, txn)
    txn._cache = cache
    ob = create_content()
    parent = create_content()
    ob.__parent__ = parent
    storage.store(parent)
    storage.store(ob)

    loaded = await txn.get_child(parent, ob.id)
    assert len(cache._actions) == 1
    assert cache._actions[0]['action'] == 'stored'
    loaded = await txn.get_child(parent, ob.id)
    assert cache._actions[-1]['action'] == 'loaded'

    assert id(loaded) != id(ob)
    assert loaded._p_oid == ob._p_oid


async def test_do_not_cache_large_object(dummy_guillotina):
    tm = mocks.MockTransactionManager()
    storage = tm._storage
    txn = Transaction(tm)
    cache = MemoryCache(storage, txn)
    txn._cache = cache
    ob = create_content()
    ob.foobar = 'X' * cache.max_cache_record_size  # push size above cache threshold
    storage.store(ob)
    loaded = await txn.get(ob._p_oid)
    assert id(loaded) != id(ob)
    assert loaded._p_oid == ob._p_oid
    assert len(cache._actions) == 0
