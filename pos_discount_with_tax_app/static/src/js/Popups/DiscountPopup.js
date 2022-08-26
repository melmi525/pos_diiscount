odoo.define('pos_discount_with_tax.DiscountPopup', function (require) {
	'use strict';

	var core = require('web.core');
	const { useState, useRef } = owl.hooks;
	const { useListener } = require('web.custom_hooks');
	const PosComponent = require('point_of_sale.PosComponent');
	const Registries = require('point_of_sale.Registries');
	const AbstractAwaitablePopup = require('point_of_sale.AbstractAwaitablePopup');
	var QWeb = core.qweb;
	var _t = core._t;

	class DiscountTypePopup extends AbstractAwaitablePopup {
		constructor() {
			super(...arguments);
			$('input.dicount_type').on('change', function() {
				$('input.dicount_type').not(this).prop('checked', false);  
			});
		}
		click_confirm(){
			var order = this.env.pos.get_order();
			var orderlines = order.get_orderlines();
			var selected = $("input.dicount_type:checked").attr("id");
			if(order.discount_on == 'order')
			{
				if(selected == 'fixed')
				{
					order.set_order_discount_type('fixed');
				}
				else{
					order.set_order_discount_type('percentage');
				}
			}
			else{

				if(selected == 'fixed')
				{
					
					order.get_selected_orderline().is_line_discount = true;
					order.get_selected_orderline().set_orderline_discount_type('fixed');
				}
				else{
					order.get_selected_orderline().is_line_discount = true;
					order.get_selected_orderline().set_orderline_discount_type('percentage');
				}
			}
			this.trigger('close-popup');
		}

		click_cancel(){
			this.trigger('close-popup');
		}
	}

	DiscountTypePopup.template = 'DiscountTypePopup';
	DiscountTypePopup.defaultProps = {
        confirmText: 'Ok',
        cancelText: 'Cancel',
        title: 'Select Discount Type',
        body: '',
        list: [],
        startingValue: '',
    };

	Registries.Component.add(DiscountTypePopup);

	return DiscountTypePopup;
});
