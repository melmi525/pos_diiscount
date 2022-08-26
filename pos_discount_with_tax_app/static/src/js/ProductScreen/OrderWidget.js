odoo.define('pos_discount_with_tax_app.OrderWidget', function(require) {
	'use strict';

	const { useState, useRef, onPatched } = owl.hooks;
	const { useListener } = require('web.custom_hooks');
	const { onChangeOrder } = require('point_of_sale.custom_hooks');
	const PosComponent = require('point_of_sale.PosComponent');
	const Registries = require('point_of_sale.Registries');
	const OrderWidget = require('point_of_sale.OrderWidget');

	const PosDisOrderWidget = (OrderWidget) =>
		class extends OrderWidget{
			constructor() {
				super(...arguments);
				this.state = useState({ total: 0, tax: 0, discount: 0});
			}
			_updateSummary() {
				const order_discount = this.order ? this.order.get_order_discount() : 0;
				const total = this.order ? this.order.get_total_with_tax() : 0;
				const subtotal = this.order ? this.order.get_total_without_tax() : 0;
				const tax = this.order ? total - this.order.get_total_without_tax() + order_discount : 0;
				this.state.discount = this.env.pos.format_currency(order_discount);
				this.state.total = this.env.pos.format_currency(total);
				this.state.tax = this.env.pos.format_currency(tax);
				this.state.subtotal = this.env.pos.format_currency(subtotal);
				this.render();
			}
		};
	Registries.Component.extend(OrderWidget, PosDisOrderWidget);

	return PosDisOrderWidget;
});