odoo.define('pos_eposprintt.epsonFP', function(require) {
"use strict";

var devices = require('point_of_sale.devices');
var screens = require('point_of_sale.screens');
var core = require('web.core');

var Class = require('web.Class');


var _t = core._t;

devices.ProxyDevice.include({
    print_receipt: function(receipt) { 
        this._super(receipt);
        
		var fp90 = new Driver();
		
		var receipt_obj = this.pos.get_order();
		console.log(receipt_obj);
		fp90.printFiscalReceipt(receipt_obj);
    },
});

var Driver = Class.extend({
		init: function(options) {
			console.log(options);
			options = options || {};
			var url = options.url || 'http://192.168.1.231/cgi-bin/fpmate.cgi';
			this.fiscalPrinter = new epson.fiscalPrint();
			this.fiscalPrinter.onreceive = function(res, tag_list_names, add_info) {
				console.log(res);
				console.log(tag_list_names);
				console.log(add_info);
			}
			this.fiscalPrinter.onerror = function() {
				alert('HTTP/timeout or other net error. This is not a fiscal printer internal error!');
			}
		},

		/*
		  Prints a sale item line.
		*/
		printRecItem: function(args) {
			var tag = '<printRecItem'
				+ ' description="' + (args.description || '') + '"'
				+ ' quantity="' + (args.quantity || '1') + '"'
				+ ' unitPrice="' + (args.unitPrice || '') + '"'
				+ ' department="' + (args.department || '1') + '"'
				+ ' justification="' + (args.justification || '1') + '"'
				+ ' operator="' + (args.operator || '1') + '"'
				+ ' />';
			return tag;
		},

		/*
		  Adds a discount to the last line.
		*/
		printRecItemAdjustment: function(args) {
			var tag = '<printRecItemAdjustment'
				+ ' operator="' + (args.operator || '1') + '"'
				+ ' adjustmentType="' + (args.adjustmentType || 0) + '"'
				+ ' description="' + (args.description || '' ) + '"'
				+ ' amount="' + (args.amount || '') + '"'
				// + ' department="' + (args.department || '') + '"'
				+ ' justification="' + (args.justification || '2') + '"'
				+ ' />';
			return tag;
		},

		/*
		  Prints a payment.
		*/
		printRecTotal: function(args) {
			var tag = '<printRecTotal'
				+ ' operator="' + (args.operator || '1') + '"'
				+ ' description="' + (args.description || 'Pagamento') + '"'
				+ ' payment="' + (args.payment || '') + '"'
				+ ' paymentType="' + (args.paymentType || '0') + '"'
				+ ' />';
			return tag;
		},

		/*
		  Prints a receipt
		*/
		printFiscalReceipt: function(receipt) {
			var self = this;
			var l;
			//console.log(receipt);
			var url =  'http://192.168.1.231/cgi-bin/fpmate.cgi';
			var xml = '<printerFiscalReceipt><beginFiscalReceipt />';
			console.log(receipt.orderlines);
			_.each(receipt.orderlines.models, function(l) {
				console.log('START');
				console.log(l.price);
				console.log('END');
			//	});
			//_.each(receipt.orderlines, function( l, i, list) {
				xml += self.printRecItem({
					description: l.product.display_name,
					quantity: l.quantity,
					unitPrice: l.price,
				});
				//if (l.discount) {
				//	xml += self.printRecItemAdjustment({
				//		adjustmentType: 0,
				//		description: 'Sconto ' + l.discount + '%',
				//		amount: l.quantity * l.price - l.price_display,
				//	});
				//test}
			});
			_.each(receipt.paymentlines.models, function(l) {
				xml += self.printRecTotal({
					payment: l.amount,
					paymentType: l.type,
					description: l.journal,
				});
			});
			xml += '<endFiscalReceipt /></printerFiscalReceipt>';
			this.fiscalPrinter.send(url, xml);
			console.log(xml);
		},

		printFiscalReport: function() {
			var url =  'http://192.168.1.231/cgi-bin/fpmate.cgi';
			var xml = '<printerFiscalReport>';
			xml += '<displayText operator="1" data="Chiusura fiscale" />';
			xml += '<printXZReport operator="1" />';
			xml += '</printerFiscalReport>';
			this.fiscalPrinter.send(url, xml);
		},

	});

var FiscCloseButton = screens.ActionButtonWidget.extend({
    template: 'FiscCloseButton',
    button_click: function() {
        //if (this.pos.old_receipt) {
        //    this.pos.proxy.print_receipt(this.pos.old_receipt);
        //} else {
        //    this.gui.show_popup('error', {
        //        'title': _t('Nothing to Print'),
        //        'body':  _t('There is no previous receipt to print.'),
        //    });
        if ( confirm (
        this.gui.show_popup('error', {
                'title': _t('Fiscal Close'),
                'body':  _t('Effettuare davvero la chiusura fiscale?'),
            }
            ))){
				var p = new Driver();
				p.printFiscalReport();
				} ;                      
    },
});



screens.define_action_button({
    'name': 'pos_eposprintt',
    'widget': FiscCloseButton,
    'condition': function(){
        return this.pos.config.iface_reprint && this.pos.config.iface_print_via_proxy;
    },
});
});
