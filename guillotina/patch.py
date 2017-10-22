from guillotina.profile import profilable
from zope.interface import providedBy
from zope.interface.adapter import AdapterLookupBase
from zope.interface.adapter import BaseAdapterRegistry

import asyncio


BaseAdapterRegistry._delegated = (
    'lookup', 'queryMultiAdapter', 'lookup1', 'queryAdapter',
    'adapter_hook', 'lookupAll', 'names',
    'subscriptions', 'subscribers', 'asubscribers')


@profilable
async def asubscribers(self, objects, provided):
    subscriptions = self.subscriptions(map(providedBy, objects), provided)
    afuncs = []
    if provided is None:
        for subscription in subscriptions:
            if asyncio.iscoroutinefunction(subscription):
                afuncs.append(subscription(*objects))
            else:
                subscription(*objects)
    else:
        for subscription in subscriptions:
            if asyncio.iscoroutinefunction(subscription):
                afuncs.append(subscription(*objects))
            else:
                subscription(*objects)
    await asyncio.gather(*afuncs)


@profilable
def subscribers(self, objects, provided):
    subscriptions = self.subscriptions(map(providedBy, objects), provided)
    if provided is None:
        result = ()
        for subscription in subscriptions:
            if not asyncio.iscoroutinefunction(subscription):
                subscription(*objects)
    else:
        result = []
        for subscription in subscriptions:
            if not asyncio.iscoroutinefunction(subscription):
                subscriber = subscription(*objects)
                if subscriber is not None:
                    result.append(subscriber)
    return result


AdapterLookupBase.asubscribers = asubscribers
AdapterLookupBase.subscribers = subscribers
