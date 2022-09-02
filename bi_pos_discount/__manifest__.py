# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    "name": "POS Discount Percentage and Fixed Amount in Odoo",
    "version": "15.0.0.4",
    "category": "Point of Sale",
    "depends": ['base', 'sale', 'point_of_sale'],
    "author": "BrowseInfo",
    'summary': 'Point Of Sales discount on POS Discount Amount Display POS Discount Coupons POS Custom Discount pos fix discount pos offers POS Global Discount point of sales fixed POS global Discount on POS order Discount on POS Discount Coupons on pos',
    "description": """
    
    Purpose :-
	pos discount 
	point of sales discount 
	pos fixed discount
	pos Percentage wise discount
This Module allow us to add Custom Discounts on particular order.
    POS Discount POS global Discount, POS Globel Discount, Global discount on POS order ,
    POS order discount, Point of sale order discount, apply discount on POS Order, Apply discount on point of sale.
    Mutiple discount on POS Order, POS custom discount, custom discount on POS Order, Custom discount on Point of Sale.
    manage discount on POS, Discount on POS order line, Discount on Point of sale line

    Manages the Discount in pos order line and in whole pos order basis on Fix
and Percentage wise as well as calculate tax before discount and after
discount and same for the Invoice.Disount on POS order, Discount on point of sale Discount on orders, order discount
    POS Global Discount
    POS fixed discount POS percentage discount, fixed discount on POS, percentage discount on POS
    point of sale fixed discount,point of sale percentage discount, fixed discount on point of sale, percentage discount on point of sale
    point of sale Global Discount
    point of sale custom discount
    point of sale discount


This Module allow us to add Custom Discounts on particular order.
    odoo POS Discount POS global Discount POS Globel Discount Global discount on POS order
    odoo POS order discount Point of sale order discount apply discount on POS Order Apply discount on point of sale.
    odoo multiple discount on POS Order POS custom discount custom discount on POS Order Custom discount on Point of Sale.
    odoo manage discount on POS Discount on POS order line Discount on Point of sale line pos custom discount
    point of sales custom discount
    odoo pos custom discount custom discount on pos 
    Manages the Discount in pos order line and in whole pos order basis on Fix
and Percentage wise as well as calculate tax before discount and after
discount and same for the Invoice.Disount on POS order Discount on point of sale Discount on orders
order discount POS Global Discount
    odoo POS fixed discount POS percentage discount fixed discount on POS percentage discount on POS
    odoo point of sale fixed discount point of sale percentage discount fixed discount on point of sale
    odoo percentage discount on point of sale point of sale Global Discount point of sale custom discount point of sale discount
    """,
    "price": 22,
    "currency": 'EUR',
    "website": "https://www.browseinfo.in",
    "data": [
        'views/custom_pos_view.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'bi_pos_discount/static/src/js/pos.js',
            'bi_pos_discount/static/src/js/DiscountOrderReceipt.js',
            'bi_pos_discount/static/src/js/BiTicketScreen.js',
        ],
        'web.assets_qweb': [
            'bi_pos_discount/static/src/xml/**/*',
        ],
    },
    "auto_install": False,
    "installable": True,
    "live_test_url": "https://youtu.be/_zfPH_JdSg0",
    "images": ['static/description/Banner.png'],
    'license': 'OPL-1',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
