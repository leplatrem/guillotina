# -*- coding: utf-8 -*-
from guillotina.behaviors.attachment import IAttachment
from guillotina.testing import GuillotinaFunctionalTestCase
from guillotina.tests import TEST_RESOURCES_DIR
from zope import schema
from zope.interface import Interface

import json
import os


class ITestingRegistry(Interface):
    enabled = schema.Bool(
        title="Example attribute")


class FunctionalTestServer(GuillotinaFunctionalTestCase):
    """Functional testing of the API REST."""

    def _get_site(self):
        """
        sometimes the site does not get updated data from zodb
        this seems to make it
        """
        return self.new_root()['guillotina']

    def test_get_root(self):
        """Get the application root."""
        resp = self.layer.requester('GET', '/')
        response = json.loads(resp.text)
        self.assertEqual(response['static_file'], ['favicon.ico'])
        self.assertEqual(response['databases'], ['guillotina'])
        self.assertEqual(response['static_directory'], [])

    def test_get_database(self):
        """Get the database object."""
        resp = self.layer.requester('GET', '/guillotina')
        response = json.loads(resp.text)
        self.assertTrue(len(response['sites']) == 1)

    def test_get_guillotina(self):
        """Get the root guillotina site."""
        resp = self.layer.requester('GET', '/guillotina/guillotina')
        response = json.loads(resp.text)
        self.assertTrue(len(response['items']) == 0)

    def test_get_contenttypes(self):
        """Check list of content types."""
        resp = self.layer.requester('GET', '/guillotina/guillotina/@types')
        self.assertTrue(resp.status_code == 200)
        response = json.loads(resp.text)
        self.assertTrue(len(response) > 1)
        self.assertTrue(any("Item" in s['title'] for s in response))
        self.assertTrue(any("Site" in s['title'] for s in response))

    def test_get_contenttype(self):
        """Get a content type definition."""
        resp = self.layer.requester('GET', '/guillotina/guillotina/@types/Item')
        self.assertTrue(resp.status_code == 200)
        response = json.loads(resp.text)
        self.assertTrue(len(response['definitions']), 1)
        self.assertTrue(response['title'] == 'Item')

    def test_get_registries(self):
        """Get the list of registries."""
        resp = self.layer.requester('GET', '/guillotina/guillotina/@registry')
        self.assertTrue(resp.status_code == 200)
        response = json.loads(resp.text)['value']
        self.assertTrue(len(response) == 2)
        self.assertTrue(
            'guillotina.registry.ILayers.active_layers' in response)

    def test_get_registry(self):
        """Check a value from registry."""
        resp = self.layer.requester(
            'GET',
            '/guillotina/guillotina/@registry/guillotina.registry.ILayers.active_layers')
        response = json.loads(resp.text)
        self.assertTrue(response)

    def test_create_contenttype(self):
        """Try to create a contenttype."""
        resp = self.layer.requester(
            'POST',
            '/guillotina/guillotina/',
            data=json.dumps({
                "@type": "Item",
                "title": "Item1",
                "id": "item1"
            })
        )
        self.assertTrue(resp.status_code == 201)
        root = self.new_root()
        obj = root['guillotina']['item1']
        self.assertEqual(obj.title, 'Item1')

    def test_create_delete_contenttype(self):
        """Create and delete a content type."""
        resp = self.layer.requester(
            'POST',
            '/guillotina/guillotina/',
            data=json.dumps({
                "@type": "Item",
                "title": "Item1",
                "id": "item1"
            })
        )
        self.assertTrue(resp.status_code == 201)
        resp = self.layer.requester('DELETE', '/guillotina/guillotina/item1')
        self.assertTrue(resp.status_code == 200)

    def test_register_registry(self):
        """Try to create a contenttype."""
        resp = self.layer.requester(
            'POST',
            '/guillotina/guillotina/@registry',
            data=json.dumps({
                "interface": "guillotina.tests.test_api.ITestingRegistry",
                "initial_values": {
                    "enabled": True
                }
            })
        )
        self.assertTrue(resp.status_code == 201)

        resp = self.layer.requester(
            'PATCH',
            '/guillotina/guillotina/@registry/guillotina.tests.test_api.ITestingRegistry.enabled',
            data=json.dumps({
                "value": False
            })
        )
        self.assertTrue(resp.status_code == 204)
        resp = self.layer.requester(
            'GET',
            '/guillotina/guillotina/@registry/guillotina.tests.test_api.ITestingRegistry.enabled')
        response = json.loads(resp.text)
        self.assertEqual({'value': False}, response)

    def test_file_upload(self):
        resp = self.layer.requester(
            'POST',
            '/guillotina/guillotina/',
            data=json.dumps({
                "@type": "File",
                "title": "File1",
                "id": "file1"
            })
        )
        self.assertTrue(resp.status_code == 201)
        site = self._get_site()
        self.assertTrue('file1' in site)
        fi = open(os.path.join(TEST_RESOURCES_DIR, 'plone.png'), 'rb')
        data = fi.read()
        fi.close()
        resp = self.layer.requester(
            'PATCH',
            '/guillotina/guillotina/file1/@upload/file',
            data=data)
        site = self._get_site()
        behavior = IAttachment(site['file1'])
        self.assertEqual(behavior.file.data, data)

    def test_file_download(self):
        # first, get a file on...
        self.test_file_upload()
        resp = self.layer.requester(
            'GET',
            '/guillotina/guillotina/file1/@download/file')
        site = self._get_site()
        behavior = IAttachment(site['file1'])
        self.assertEqual(behavior.file.data, resp.content)

    def test_create_contenttype_with_date(self):
        """Try to create a contenttype."""
        resp = self.layer.requester(
            'POST',
            '/guillotina/guillotina/',
            data=json.dumps({
                "@type": "Item",
                "title": "Item1",
                "id": "item1",
            })
        )
        self.assertTrue(resp.status_code == 201)
        date_to_test = "2016-11-30T14:39:07.394273+01:00"
        resp = self.layer.requester(
            'PATCH',
            '/guillotina/guillotina/item1',
            data=json.dumps({
                "guillotina.behaviors.dublincore.IDublinCore": {
                    "created": date_to_test,
                    "expires": date_to_test
                }
            })
        )

        root = self.new_root()
        obj = root['guillotina']['item1']
        from guillotina.behaviors.dublincore import IDublinCore
        self.assertEqual(IDublinCore(obj).created.isoformat(), date_to_test)
        self.assertEqual(IDublinCore(obj).expires.isoformat(), date_to_test)

    def test_create_duplicate_id(self):
        """Try to create a contenttype."""
        resp = self.layer.requester(
            'POST',
            '/guillotina/guillotina/',
            data=json.dumps({
                "@type": "Item",
                "title": "Item1",
                "id": "item1",
            })
        )
        self.assertTrue(resp.status_code == 201)
        resp = self.layer.requester(
            'POST',
            '/guillotina/guillotina/',
            data=json.dumps({
                "@type": "Item",
                "title": "Item1",
                "id": "item1",
            })
        )
        self.assertTrue(resp.status_code == 409)
        resp = self.layer.requester(
            'POST',
            '/guillotina/guillotina/',
            data=json.dumps({
                "@type": "Item",
                "title": "Item1",
                "id": "item1",
            }),
            headers={
                "OVERWRITE": "TRUE"
            }
        )
        self.assertTrue(resp.status_code == 201)

    def test_create_nested_object(self):
        resp = self.layer.requester(
            'POST',
            '/guillotina/guillotina/',
            data=json.dumps({
                '@type': 'Example',
                'title': 'Item1',
                'id': 'item1',
                'categories': [{
                    'label': 'term1',
                    'number': 1.0
                }, {
                    'label': 'term2',
                    'number': 2.0
                }]
            })
        )
        self.assertTrue(resp.status_code == 201)

    def test_get_addons(self):
        resp = self.layer.requester(
            'GET', '/guillotina/guillotina/@addons'
        )
        self.assertEqual(resp.status_code, 200)
