odoo.define('pos_discount_with_tax.SelectDiscountPopup', function (require) {
	'use strict';

	var core = require('web.core');
	const { useState, useRef } = owl.hooks;
	const { useListener } = require('web.custom_hooks');
	const PosComponent = require('point_of_sale.PosComponent');
	const Registries = require('point_of_sale.Registries');
	const AbstractAwaitablePopup = require('point_of_sale.AbstractAwaitablePopup');
	var QWeb = core.qweb;
	var _t = core._t;

	class SelectDiscountPopup extends AbstractAwaitablePopup {
		constructor() {
			super(...arguments);
			$('input.dicount_type').on('change', function() {
				$('input.dicount_type').not(this).prop('checked', false);  
			});
		}

		click_confirm(){
			var order = this.env.pos.get_order();
			var orderlines = order.get_orderlines();
			var selected = $("input.discount_on:checked").attr("id");
			if(selected == 'on_order')
			{
				if(order.discount_on  == 'orderline')
				{
					orderlines.forEach(function (line) {
						line.discount = 0.0;
						line.discountStr = '0';
						line.orderline_discount_type = '';
						line.set_disc_str();
						line.is_line_discount =false;
					});
				}
				$('.discount-btn').text('Discount On Order')
				order.set_discount_on('order');
			}
			else{
				if(order.discount_on  == 'order')
				{
					order.set_order_discount(0.0)
					order.order_discount_type = '';
				}
				$('.discount-btn').text('Discount On OrderLine')
				order.set_discount_on('orderline');
			}
			this.trigger('close-popup');
		}
		click_cancel(){
			this.trigger('close-popup');
		}
	}

	SelectDiscountPopup.template = 'SelectDiscountPopup';
	SelectDiscountPopup.defaultProps = {
        confirmText: 'Ok',
        cancelText: 'Cancel',
        title: '',
        body: '',
        list: [],
        startingValue: '',
    };

	Registries.Component.add(SelectDiscountPopup);

	return SelectDiscountPopup;
});
