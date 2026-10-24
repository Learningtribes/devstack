"""Verify safe XML wrapper preserves SAML parser entity rejection."""
import unittest
from safe_lxml import defuse_xml_libs
defuse_xml_libs()
from lxml import etree
from defusedxml.common import EntitiesForbidden
from onelogin.saml2.xmlparser import fromstring, DTDForbidden
from onelogin.saml2.auth import OneLogin_Saml2_Auth

class XMLTests(unittest.TestCase):
    def test_safe_wrapper_rejects_entity(self):
        with self.assertRaises(EntitiesForbidden):
            etree.fromstring('<!DOCTYPE root [<!ENTITY local "value">]><root>&local;</root>')

    def test_saml_parser_rejects_dtd(self):
        with self.assertRaises(DTDForbidden):
            fromstring('<!DOCTYPE root><root/>')

    def test_saml_parser_plain_xml(self):
        root = fromstring('<root><child>value</child></root>')
        self.assertEqual(root[0].text, 'value')
        self.assertIsNotNone(OneLogin_Saml2_Auth)

if __name__ == '__main__':
    unittest.main(verbosity=2)
