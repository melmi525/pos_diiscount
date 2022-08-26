odoo.define('pos_discount_with_tax_app.OrderDiscountButton', function(require) {
	'use strict';

	const PosComponent = require('point_of_sale.PosComponent');
	const ProductScreen = require('point_of_sale.ProductScreen');
	const { useListener } = require('web.custom_hooks');
	const Registries = require('point_of_sale.Registries');

	class OrderDiscountButton extends PosComponent {
		constructor() {
			super(...arguments);
			useListener('click', this.onClick);
		}
		async onClick() {
			this.showPopup('SelectDiscountPopup', {
				title: this.env._t('Select Discount Type'),
			});

		}
	}

	OrderDiscountButton.template = 'OrderDiscountButton';

	ProductScreen.addControlButton({
		component: OrderDiscountButton,
		condition: function() {
			return this.env.pos.config.allow_order_disc;
		},
	});

	Registries.Component.add(OrderDiscountButton);

	return OrderDiscountButton;
});