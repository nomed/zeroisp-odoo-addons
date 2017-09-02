# -*- coding: utf-8 -*-
from odoo import http

# class HwGeneric(http.Controller):
#     @http.route('/hw_generic/hw_generic/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/hw_generic/hw_generic/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('hw_generic.listing', {
#             'root': '/hw_generic/hw_generic',
#             'objects': http.request.env['hw_generic.hw_generic'].search([]),
#         })

#     @http.route('/hw_generic/hw_generic/objects/<model("hw_generic.hw_generic"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('hw_generic.object', {
#             'object': obj
#         })