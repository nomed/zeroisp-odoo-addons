# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'fiscal ePOS-Print XML Proxy',
    'version': '1.0',
    'category': 'Point of Sale',
    'sequence': 6,
    'website': 'https://www.odoo.com/page/point-of-sale',
    'summary': 'Hardware Driver for fiscal ePOS-Print XML',
    'description': """

Hardware Driver for fiscal ePOS-Print
========================================

This module contains drivers to connect Odoo and ePos-Print compatible fiscal printer according to Italian laws.


""",
    'depends': ['hw_proxy',  'point_of_sale'],
    'author': 'Daniele Favara @ Zeroisp',
    'website': 'http://www.zeroisp.com',    
    #'external_dependencies': {
    #    'python' : ['usb.core','serial','qrcode'],
    #},
    'test': [
    ],
    'data': ['views/hw_eposprint.xml', 'security/ir.model.access.csv',],
    
    'installable': True,
    'auto_install': False,
}
