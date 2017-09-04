# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


# class hw_generic(models.Model):
#     _name = 'hw_generic.hw_generic'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         self.value2 = float(self.value) / 100

# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HwGenericConfig(models.Model):
    _inherit = 'pos.config'

    #iface_splitbill = fields.Boolean(string='Bill Splitting', help='Enables Bill Splitting in the Point of Sale')
    #iface_printbill = fields.Boolean(string='Bill Printing', help='Allows to print the Bill before payment')
    #iface_orderline_notes = fields.Boolean(string='Orderline Notes', help='Allow custom notes on Orderlines')
    #floor_ids = fields.One2many('restaurant.floor', 'pos_config_id', string='Restaurant Floors', help='The restaurant floors served by this point of sale')
    printer_ids = fields.Many2many('hw_generic.printer', 'pos_config_printer_rel', 'config_id', 'printer_id', string='Generic Printers')

class HwGenericPrinter(models.Model):
    
    _name = 'hw_generic.printer'

    name = fields.Char('Printer Name', required=True, default='Printer', help='An internal identification of the printer')
    host = fields.Char('Printer IP', required=True, default='Printer', help='IP of the printer')
    proxy_ip = fields.Char('Proxy IP Address', help="The IP Address or hostname of the Printer's hardware proxy")    

