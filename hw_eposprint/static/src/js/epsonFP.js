odoo.define('hw_eposprint.epsonFP', function(require) {
"use strict";


var screens = require('point_of_sale.screens');


screens.ReceiptScreenWidget.include({
    print_xml: function() {
        var env = {
            widget:  this,
            pos:     this.pos,
            order:   this.pos.get_order(),
            receipt: this.pos.get_order().export_for_printing(),
            paymentlines: this.pos.get_order().get_paymentlines()
        };
        //var receipt = QWeb.render('XmlReceipt',env);
        var receipt = env.receipt;
        console.log(receipt);
        this.pos.proxy.print_receipt(receipt);
        this.pos.get_order()._printed = true;
    },
});


});
