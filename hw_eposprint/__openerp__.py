# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'fiscal ePOS-Print XML Proxy',
    'version': '1.0',
    'category': 'Hardware Drivers',
    'sequence': 6,
    'website': 'https://www.odoo.com/page/point-of-sale',
    'summary': 'Hardware Driver for fiscal ePOS-Print XML',
    'description': """
Hardware Driver for fiscal ePOS-Print
========================================

""",
    'depends': ['hw_proxy'],
    'author': 'Daniele Favara @ Zeroisp',
    'website': 'http://www.zeroisp.com',    
    #'external_dependencies': {
    #    'python' : ['usb.core','serial','qrcode'],
    #},
    'test': [
    ],
    'data': ['views/hw_eposprint.xml'],
    
    'installable': True,
    'auto_install': False,
}
