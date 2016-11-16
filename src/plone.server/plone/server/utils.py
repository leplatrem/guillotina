# -*- coding: utf-8 -*-
from aiohttp.web_exceptions import HTTPUnauthorized
from plone.server import CORS

import fnmatch
import importlib


def import_class(import_string):
    t = import_string.rsplit('.', 1)
    return getattr(importlib.import_module(t[0]), t[1], None)


def get_content_path(content):
    """ No site id
    """
    parts = []
    parent = getattr(content, '__parent__', None)
    while content is not None and content.__name__ is not None and\
            parent is not None:
        parts.append(content.__name__)
        content = parent
        parent = getattr(content, '__parent__', None)
    return '/' + '/'.join(reversed(parts))


def iter_parents(content):
    content = getattr(content, '__parent__', None)
    while content:
        yield content
        content = getattr(content, '__parent__', None)


def get_authenticated_user_id(request):
    if hasattr(request, 'security') and hasattr(request.security, 'participations') \
            and len(request.security.participations) > 0:
        return request.security.participations[0].principal.id
    else:
        return None


async def apply_cors(request):
    """Second part of the cors function to validate."""
    headers = {}
    origin = request.headers.get('Origin', None)
    if origin:
        if not any([fnmatch.fnmatchcase(origin, o)
           for o in CORS['allow_origin']]):
            raise HTTPUnauthorized('Origin %s not allowed' % origin)
        elif request.headers.get('Access-Control-Allow-Credentials', False):
            headers['Access-Control-Allow-Origin', origin]
        else:
            if any([o == "*" for o in CORS['allow_origin']]):
                headers['Access-Control-Allow-Origin'] = '*'
            else:
                headers['Access-Control-Allow-Origin'] = origin
    if request.headers.get(
            'Access-Control-Request-Method', None) != 'OPTIONS':
        if CORS['allow_credentials']:
            headers['Access-Control-Allow-Credentials'] = 'True'
        if len(CORS['allow_headers']):
            headers['Access-Control-Expose-Headers'] = \
                ', '.join(CORS['allow_headers'])
    return headers


def strings_differ(string1, string2):
    """Check whether two strings differ while avoiding timing attacks.

    This function returns True if the given strings differ and False
    if they are equal.  It's careful not to leak information about *where*
    they differ as a result of its running time, which can be very important
    to avoid certain timing-related crypto attacks:

        http://seb.dbzteam.org/crypto/python-oauth-timing-hmac.pdf

    """
    if len(string1) != len(string2):
        return True

    invalid_bits = 0
    for a, b in zip(string1, string2):
        invalid_bits += a != b

    return invalid_bits != 0


class Lazy(object):
    """Lazy Attributes."""

    def __init__(self, func, name=None):
        if name is None:
            name = func.__name__
        self.data = (func, name)

    def __get__(self, inst, class_):
        if inst is None:
            return self

        func, name = self.data
        value = func(inst)
        inst.__dict__[name] = value

        return value