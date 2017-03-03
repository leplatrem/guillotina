# -*- coding: utf-8 -*-
from aiohttp import web
from datetime import datetime
from datetime import timedelta
from guillotina import app_settings
from guillotina import configure
from guillotina import jose
from guillotina import logger
from guillotina.api.service import Service
from guillotina.browser import Response
from guillotina.interfaces import IInteraction
from guillotina.interfaces import IPermission
from guillotina.interfaces import ISite
from guillotina.interfaces import ITraversableView
from zope.component import getUtility
from zope.component import queryMultiAdapter

import aiohttp
import asyncio
import ujson


@configure.service(context=ISite, method='GET', permission='guillotina.AccessContent',
                   name='@wstoken')
class WebsocketGetToken(Service):
    _websockets_ttl = 60

    def generate_websocket_token(self, real_token):
        exp = datetime.utcnow() + timedelta(
            seconds=self._websockets_ttl)

        claims = {
            'iat': int(datetime.utcnow().timestamp()),
            'exp': int(exp.timestamp()),
            'token': real_token
        }
        jwe = jose.encrypt(claims, app_settings['rsa']['priv'])
        token = jose.serialize_compact(jwe)
        return token.decode('utf-8')

    async def __call__(self):
        # Get token
        header_auth = self.request.headers.get('AUTHORIZATION')
        token = None
        if header_auth is not None:
            schema, _, encoded_token = header_auth.partition(' ')
            if schema.lower() == 'basic' or schema.lower() == 'bearer':
                token = encoded_token.encode('ascii')

        # Create ws token
        new_token = self.generate_websocket_token(token)
        return {
            "token": new_token
        }


@configure.service(context=ISite, method='GET', permission='guillotina.AccessContent',
                   name='@ws')
class WebsocketsView(Service):

    async def __call__(self):
        ws = web.WebSocketResponse()
        await ws.prepare(self.request)

        async for msg in ws:
            if msg.tp == aiohttp.MsgType.text:
                message = ujson.loads(msg.data)
                if message['op'] == 'close':
                    await ws.close()
                elif message['op'] == 'GET':
                    method = app_settings['http_methods']['GET']
                    path = tuple(p for p in message['value'].split('/') if p)

                    # avoid circular import
                    from guillotina.traversal import do_traverse

                    obj, tail = await do_traverse(
                        self.request, self.request.site, path)

                    traverse_to = None

                    if tail and len(tail) == 1:
                        view_name = tail[0]
                    elif tail is None or len(tail) == 0:
                        view_name = ''
                    else:
                        view_name = tail[0]
                        traverse_to = tail[1:]

                    permission = getUtility(
                        IPermission, name='guillotina.AccessContent')

                    allowed = IInteraction(self.request).check_permission(
                        permission.id, obj)
                    if not allowed:
                        response = {
                            'error': 'Not allowed'
                        }
                        ws.send_str(ujson.dumps(response))

                    try:
                        view = queryMultiAdapter(
                            (obj, self.request), method, name=view_name)
                    except AttributeError:
                        view = None

                    if traverse_to is not None:
                        if view is None or not ITraversableView.providedBy(view):
                            response = {
                                'error': 'Not found'
                            }
                            ws.send_str(ujson.dumps(response))
                        else:
                            try:
                                view = view.publishTraverse(traverse_to)
                            except Exception as e:
                                logger.error(
                                    "Exception on view execution",
                                    exc_info=e)
                                response = {
                                    'error': 'Not found'
                                }
                                ws.send_str(ujson.dumps(response))

                    view_result = await view()
                    if isinstance(view_result, Response):
                        view_result = view_result.response

                    # Return the value
                    ws.send_str(ujson.dumps(view_result))

                    # Wait for possible value
                    futures_to_wait = self.request._futures.values()
                    if futures_to_wait:
                        await asyncio.gather(futures_to_wait)
                        self.request._futures = {}
                else:
                    await ws.close()
            elif msg.tp == aiohttp.MsgType.error:
                logger.debug('ws connection closed with exception {0:s}'
                             .format(ws.exception()))

        logger.debug('websocket connection closed')

        return {}