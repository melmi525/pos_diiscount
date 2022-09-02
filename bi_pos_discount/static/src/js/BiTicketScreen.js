odoo.define('bi_pos_discount.BiTicketScreen', function(require) {
	'use strict';

	const TicketScreen = require('point_of_sale.TicketScreen');
	const Registries = require('point_of_sale.Registries');
	let check_do = true;

	const BiTicketScreen = (TicketScreen) =>
		class extends TicketScreen {
			constructor() {
				super(...arguments);
			}

			_getToRefundDetail(orderline) {
	            if (orderline.id in this.env.pos.toRefundLines) {
	                return this.env.pos.toRefundLines[orderline.id];
	            } else {
	                const customer = orderline.order.get_client();
	                const orderPartnerId = customer ? customer.id : false;
	                const newToRefundDetail = {
	                    qty: 0,
	                    orderline: {
	                        id: orderline.id,
	                        productId: orderline.product.id,
	                        price: orderline.price,
	                        qty: orderline.quantity,
	                        refundedQty: orderline.refunded_qty,
	                        orderUid: orderline.order.uid,
	                        orderBackendId: orderline.order.backendId,
	                        discount_type: orderline.discount_type,
	                        orderPartnerId,
	                        tax_ids: orderline.get_taxes().map(tax => tax.id),
	                        discount: orderline.discount,
	                    },
	                    destinationOrderUid: false,
	                };
	                this.env.pos.toRefundLines[orderline.id] = newToRefundDetail;
	                return newToRefundDetail;
	            }
	        }

	        _prepareRefundOrderlineOptions(toRefundDetail) {
	            const { qty, orderline } = toRefundDetail;
	            return {
	                quantity: -qty,
	                price: orderline.price,
	                extras: { price_manually_set: true },
	                merge: false,
	                refunded_orderline_id: orderline.id,
	                discount_type: orderline.discount_type,
	                tax_ids: orderline.tax_ids,
	                discount: orderline.discount,
	            }
	        }
	};
	Registries.Component.extend(TicketScreen, BiTicketScreen);

	return TicketScreen;

});