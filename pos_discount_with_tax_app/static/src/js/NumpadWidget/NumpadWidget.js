odoo.define('pos_discount_with_tax.NumpadWidget', function (require) {
	'use strict';

	const NumpadWidget = require('point_of_sale.NumpadWidget');
	const Registries = require('point_of_sale.Registries');
	const Gui = require('point_of_sale.Gui');

	const PosDisNumpadWidget = (NumpadWidget) =>
		class extends NumpadWidget{
			constructor() {
				super(...arguments);
			}
			changeMode(mode) {
				let self = this;
				let order = this.env.pos.get_order();
				if (!this.hasPriceControlRights && mode === 'price') {
					return;
				}
				if (!this.hasManualDiscount && mode === 'discount') {
					return;
				}
				if(mode == 'discount')
				{
					if(self.env.pos.config.allow_order_disc)
					{
						if(order && order.discount_on)
						{
							this.showPopup('DiscountTypePopup', {
								body: 'Cheque',
								startingValue: self,
								title: this.env._t('Discount'),
							});
							this.trigger('set-numpad-mode', { mode });
						}
						else{
							alert('Please click on "Add Discount" and select discount on order/orderline')
						}
					}
					else{
						this.trigger('set-numpad-mode', { mode });
					}
				}
				else{
					this.trigger('set-numpad-mode', { mode });
				}
				// this.trigger('set-numpad-mode', { mode });
			}
		}

	Registries.Component.extend(NumpadWidget, PosDisNumpadWidget);

	return PosDisNumpadWidget;
});