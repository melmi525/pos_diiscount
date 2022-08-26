odoo.define('pos_discount_with_tax_app.pos', function(require) {
	"use strict";

	const models = require('point_of_sale.models');
	// var screens = require('point_of_sale.screens');
	var core = require('web.core');
	const gui = require('point_of_sale.Gui');
	// var popups = require('point_of_sale.popups');
	var QWeb = core.qweb;
	var utils = require('web.utils');
	var round_pr = utils.round_precision;
	var _t = core._t;
	var main_disc = 0.0;

	var OrderlineSuper = models.Orderline;
	models.Orderline = models.Orderline.extend({
		initialize: function(attr,options){
			OrderlineSuper.prototype.initialize.apply(this, arguments);
			this.pos   = options.pos;
			this.order = options.order;
			this.orderline_discount_type =  '';
			this.is_line_discount = false;
			if(options.json)
			{
				this.set_orderline_discount_type(options.json.orderline_discount_type);
				this.is_line_discount = options.json.is_line_discount;
			}
			
		},

		export_for_printing: function(){
			return {
				id: this.id,
				quantity:           this.get_quantity(),
				unit_name:          this.get_unit().name,
				price:              this.get_unit_display_price(),
				discount:           this.get_discount(),
				orderline_discount_type: this.orderline_discount_type,
				product_name:       this.get_product().display_name,
				product_name_wrapped: this.generate_wrapped_product_name(),
				price_lst:          this.get_lst_price(),
				display_discount_policy:    this.display_discount_policy(),
				price_display_one:  this.get_display_price_one(),
				price_display :     this.get_display_price(),
				price_with_tax :    this.get_price_with_tax(),
				price_without_tax:  this.get_price_without_tax(),
				price_with_tax_before_discount:  this.get_price_with_tax_before_discount(),
				tax:                this.get_tax(),
				product_description:      this.get_product().description,
				product_description_sale: this.get_product().description_sale,
			};
		},
		set_orderline_discount_type: function(orderline_discount_type){
			this.orderline_discount_type = orderline_discount_type;
			this.trigger('change',this);
		},

		get_orderline_discount_type: function(){
			return this.orderline_discount_type ;
		},

		set_disc_str: function(){
			this.trigger('change',this);
		},

		export_as_JSON: function() {
			var self = this;
			var loaded = OrderlineSuper.prototype.export_as_JSON.call(this);
			loaded.is_line_discount = this.is_line_discount || false;
			loaded.orderline_discount_type = this.orderline_discount_type || false;
			return loaded;
		},

		set_discount: function(discount){
			var disc = Math.min(Math.max(parseFloat(discount) || 0, 0),100);
			var order = this.order;
			if(order)
			{
				if(order.discount_on == 'order')
				{
					order.set_order_discount(disc)
					this.discount = 0;
					this.discountStr = '' + 0;
					this.orderline_discount_type = '';
					this.trigger('change',this);
				}
				else{
					if (this.orderline_discount_type == 'percentage')
					{
						disc = Math.min(Math.max(parseFloat(discount) || 0, 0),100);
					}
					else if (this.orderline_discount_type == 'fixed')
					{
						disc = parseFloat(discount);
					}
					this.discount = disc;
					this.discountStr = '' + disc;
					this.trigger('change',this);
				}

				if(order.discount_on == 'order')
				{
					$('.discount-btn').text('Discount On Order')
				}
				else if(order.discount_on == 'orderline')
				{
					$('.discount-btn').text('Discount On OrderLine')
				}
				else{
					$('.discount-btn').text('Add Discount')
				}
			}
			else{
				this.discount = disc;
				this.discountStr = '' + disc;
				this.trigger('change',this);
			}
		},

		get_base_price: function(){
			var rounding = this.pos.currency.rounding;
			if (this.orderline_discount_type == 'fixed')
			{
				return round_pr((this.get_unit_price()- this.get_discount())* this.get_quantity(), rounding);	
			}
			else{
				return round_pr(this.get_unit_price() * this.get_quantity() * (1 - this.get_discount()/100), rounding);
			}
		},

		get_all_prices: function(){
			var price_unit = this.get_unit_price() * (1.0 - (this.get_discount() / 100.0));
			
			if (this.orderline_discount_type == 'fixed')
			{
				price_unit = this.get_base_price()/this.get_quantity();		
			}
				
			var taxtotal = 0;

			var product =  this.get_product();
			var taxes_ids = product.taxes_id;
			var taxes =  this.pos.taxes;
			var taxdetail = {};
			var product_taxes = [];

			_(taxes_ids).each(function(el){
				product_taxes.push(_.detect(taxes, function(t){
					return t.id === el;
				}));
			});

			var all_taxes = this.compute_all(product_taxes, price_unit, this.get_quantity(), this.pos.currency.rounding);
			_(all_taxes.taxes).each(function(tax) {
				taxtotal += tax.amount;
				taxdetail[tax.id] = tax.amount;
			});

			return {
				"priceWithTax": all_taxes.total_included,
				"priceWithoutTax": all_taxes.total_excluded,
				"tax": taxtotal,
				"taxDetails": taxdetail,
			};
		},
	});

	var posorder_super = models.Order.prototype;
	models.Order = models.Order.extend({
		initialize: function(attr,options) {
			var self = this;
			this.discount_on = '';
			this.order_discount_type = '';
			this.discount_order = 0.0;
			if(options.json)
			{
				this.set_discount_on(options.json.discount_on);
				this.set_order_discount(options.json.discount_order);
				this.set_order_discount_type(options.json.order_discount_type);
			}
			posorder_super.initialize.call(this,attr,options);
		},

		init: function(parent, options) {
			var self = this;
			this._super(parent,options);
			this.set_discount_on();
			this.set_order_discount();
			this.set_order_discount_type();
		},

		export_as_JSON: function() {
			var self = this;
			var loaded = posorder_super.export_as_JSON.call(this);
			loaded.discount_on = this.discount_on || false;
			loaded.discount_order = this.get_order_discount() || 0.0;
			loaded.order_discount_type = this.order_discount_type || false;			
			return loaded;
		},

		set_discount_on: function(discount_on){
			this.discount_on = discount_on;
			this.trigger('change',this);
		},

		set_order_discount_type: function(order_discount_type){
			this.order_discount_type = order_discount_type;
			this.trigger('change',this);
		},

		set_order_discount: function(order_discount){
			this.discount_order = order_discount;
			this.trigger('change',this);
		},

		get_discount_on: function(){
			return this.discount_on;
		},

		get_order_discount_type: function(){
			return this.order_discount_type ;
		},

		get_order_discount: function(){
			var rounding = this.pos.currency.rounding;
			var percentage_charge = 0;
			var order = this.pos.get_order();
			if (order && order.discount_on == 'order') {
				if(order.get_total_without_tax() == 0)
				{
					this.discount_order = 0.0;
					main_disc = 0.0;
				}

				if (order.order_discount_type === 'fixed') {
					var percentage_charge = this.discount_order;
					main_disc = round_pr(percentage_charge, rounding);
					return main_disc
				}
				if (order.order_discount_type === 'percentage') {
					var order = this.pos.get_order();
					var subtotal = 0.0;
					if(this.pos.config.order_discount_on == 'taxed')
					{
						subtotal = this.get_total_without_tax() + this.get_total_tax();
					}
					else{
						subtotal = this.get_total_without_tax();
					}
					var disc = this.discount_order;
					var percentage = (subtotal * disc) /100;
					var percentage_charge = percentage;
					main_disc =  round_pr(percentage_charge, rounding);
					return main_disc;
				}else{
					return 0.0
				}
			}
			else{
				return 0.0
			}
		},
		
		get_fixed_discount: function() {
			var total=0.0;
			var i;
			for(i=0;i<this.orderlines.models.length;i++) 
			{
				if(this.orderlines.models[i].orderline_discount_type == 'fixed')
				{
					total = total + Math.min(Math.max(parseFloat(this.orderlines.models[i].discount * this.orderlines.models[i].quantity) || 0, 0),10000);
				}
				else{
					var discounted_price = (this.orderlines.models[i].price * this.orderlines.models[i].quantity) *(1.0 - (this.orderlines.models[i].discount / 100.0))
					total += (this.orderlines.models[i].price * this.orderlines.models[i].quantity) -discounted_price
				}
			}
			return total
		},

		get_total_with_tax: function() {
			var total = this.get_total_without_tax() + this.get_total_tax();
			return total - main_disc;
		},
	});
});
