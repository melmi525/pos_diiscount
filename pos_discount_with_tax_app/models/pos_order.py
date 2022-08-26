# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from odoo import api, fields, models, _
from collections import defaultdict
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT

class PosOrderLineInherit(models.Model):
	_inherit = 'pos.order.line'

	orderline_discount_type = fields.Char('Discount Type')
	is_line_discount = fields.Boolean("IS Line Discount")

	def _compute_amount_line_all(self):
		for line in self:
			fpos = line.order_id.fiscal_position_id
			tax_ids_after_fiscal_position = fpos.map_tax(line.tax_ids, line.product_id,
														 line.order_id.partner_id) if fpos else line.tax_ids
			if line.orderline_discount_type == "fixed":
				price = line.price_unit - line.discount
			else:
				price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
			taxes = tax_ids_after_fiscal_position.compute_all(price, line.order_id.pricelist_id.currency_id, line.qty,
															  product=line.product_id, partner=line.order_id.partner_id)

			line.update({
				'price_subtotal_incl': taxes['total_included'],
				'price_subtotal': taxes['total_excluded'],
			})



class PosSession(models.Model):
	_inherit='pos.session'

	@api.model
	def discount_line_move_line_get(self,data):
		res = []
		account_id = False
		value = 0.0
		for order in self.order_ids:
			if order.discount_on == 'order':
				if order.order_discount:
					if order.config_id.acc_account_id:
						account_id = order.config_id.acc_account_id.id
					value += order.order_discount

		if account_id:
			disc_data = {
				'name': 'Order Discount',
				'debit': value,
				'move_id': self.move_id.id,
				'account_id': account_id or False,
				
			}
			MoveLine = data.get('MoveLine')
			MoveLine.create(disc_data)
		return data

	def _create_account_move(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
		""" Create account.move and account.move.line records for this session.

		Side-effects include:
			- setting self.move_id to the created account.move record
			- creating and validating account.bank.statement for cash payments
			- reconciling cash receivable lines, invoice receivable lines and stock output lines
		"""
		journal = self.config_id.journal_id
		# Passing default_journal_id for the calculation of default currency of account move
		# See _get_default_currency in the account/account_move.py.
		account_move = self.env['account.move'].with_context(default_journal_id=journal.id).create({
			'journal_id': journal.id,
			'date': fields.Date.context_today(self),
			'ref': self.name,
		})
		self.write({'move_id': account_move.id})

		data = {'bank_payment_method_diffs': bank_payment_method_diffs or {}}
		data = self._accumulate_amounts(data)
		data = self._create_non_reconciliable_move_lines(data)
		data = self._create_bank_payment_moves(data)
		data = self._create_pay_later_receivable_lines(data)
		data = self._create_cash_statement_lines_and_cash_move_lines(data)
		data = self._create_invoice_receivable_lines(data)
		data = self._create_stock_output_lines(data)
		data = self.discount_line_move_line_get(data)

		if balancing_account and amount_to_balance:
			data = self._create_balancing_line(data, balancing_account, amount_to_balance)

		return data


	def _prepare_line(self, order_line):
		""" Derive from order_line the order date, income account, amount and taxes information.

		These information will be used in accumulating the amounts for sales and tax lines.
		"""
		# price = 0;
		def get_income_account(order_line):
			product = order_line.product_id
			income_account = product.with_company(order_line.company_id)._get_product_accounts()['income']
			if not income_account:
				raise UserError(_('Please define income account for this product: "%s" (id:%d).')
								% (product.name, product.id))
			return order_line.order_id.fiscal_position_id.map_account(income_account)

		tax_ids = order_line.tax_ids_after_fiscal_position\
					.filtered(lambda t: t.company_id.id == order_line.order_id.company_id.id)
		sign = -1 if order_line.qty >= 0 else 1
		if order_line.orderline_discount_type != 'percentage':
			price = sign * (order_line.price_unit - order_line.discount)
		else:
			price = sign * (order_line.price_unit * (1 - (order_line.discount or 0.0) / 100.0))
			

		# The 'is_refund' parameter is used to compute the tax tags. Ultimately, the tags are part
		# of the key used for summing taxes. Since the POS UI doesn't support the tags, inconsistencies
		# may arise in 'Round Globally'.
		check_refund = lambda x: x.qty * x.price_unit < 0
		if self.company_id.tax_calculation_rounding_method == 'round_globally':
			is_refund = all(check_refund(line) for line in order_line.order_id.lines)
		else:
			is_refund = check_refund(order_line)
		tax_data = tax_ids.compute_all(price_unit=price, quantity=abs(order_line.qty), currency=self.currency_id, is_refund=is_refund)
		taxes = tax_data['taxes']
		# For Cash based taxes, use the account from the repartition line immediately as it has been paid already
		for tax in taxes:
			tax_rep = self.env['account.tax.repartition.line'].browse(tax['tax_repartition_line_id'])
			tax['account_id'] = tax_rep.account_id.id
		date_order = order_line.order_id.date_order
		taxes = [{'date_order': date_order, **tax} for tax in taxes]
		return {
			'date_order': order_line.order_id.date_order,
			'income_account_id': get_income_account(order_line).id,
			'amount': order_line.price_subtotal,
			'taxes': taxes,
			'base_tags': tuple(tax_data['base_tags']),
		}


class PosOrderInherit(models.Model):
	_inherit = 'pos.order'

	order_discount =  fields.Float(string='Order Discount', default = 0.0, readonly=True)
	order_discount_type = fields.Char('Order Discount Type')
	discount_on = fields.Char('Discount On')

	
	def _prepare_discount_invoice_line(self):
		return {
			'product_id': self.config_id.disc_product_id.id,
			'quantity': 1,
			'discount': 0,
			'price_unit': -self.order_discount,
			'name':  self.config_id.disc_product_id.display_name,
			'tax_ids': [(6, 0,[])],
			'product_uom_id': self.config_id.disc_product_id.uom_id.id,
		}

	@api.onchange('payment_ids', 'lines')
	def _onchange_amount_all(self):
		for order in self:
			currency = order.pricelist_id.currency_id
			order.amount_paid = sum(payment.amount for payment in order.payment_ids)
			order.amount_return = sum(payment.amount < 0 and payment.amount or 0 for payment in order.payment_ids)
			order.amount_tax = currency.round(
				sum(self._amount_line_tax(line, order.fiscal_position_id) for line in order.lines))
			amount_untaxed = currency.round(sum(line.price_subtotal for line in order.lines))
			order.amount_total = order.amount_tax + amount_untaxed


	@api.model
	def _amount_line_tax(self, line, fiscal_position_id):
		taxes = line.tax_ids.filtered(lambda t: t.company_id.id == line.order_id.company_id.id)
		taxes = fiscal_position_id.map_tax(taxes)
		if line.orderline_discount_type == 'percentage':
			price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
		else:
			price = line.price_unit - line.discount
		taxes = taxes.compute_all(price, line.order_id.pricelist_id.currency_id, line.qty, product=line.product_id, partner=line.order_id.partner_id or False)['taxes']
		return sum(tax.get('amount', 0.0) for tax in taxes)

	

	@api.model
	def _order_fields(self, ui_order):
		res = super(PosOrderInherit, self)._order_fields(ui_order)
		if 'discount_on' in ui_order :
			res['discount_on'] =  ui_order['discount_on']
		if 'discount_order' in ui_order :
			res['order_discount'] =  ui_order['discount_order']
		if 'order_discount_type' in ui_order :
			res['order_discount_type'] =  ui_order['order_discount_type']
		return res


	@api.model
	def _process_order(self, order, draft, existing_order):
		"""Create or update an pos.order from a given dictionary.

		:param dict order: dictionary representing the order.
		:param bool draft: Indicate that the pos_order is not validated yet.
		:param existing_order: order to be updated or False.
		:type existing_order: pos.order.
		:returns: id of created/updated pos.order
		:rtype: int
		"""
		order = order['data']
		pos_session = self.env['pos.session'].browse(order['pos_session_id'])
		if pos_session.state == 'closing_control' or pos_session.state == 'closed':
			order['pos_session_id'] = self._get_valid_session(order).id

		pos_order = False
		if not existing_order:
			pos_order = self.create(self._order_fields(order))
		else:
			pos_order = existing_order
			pos_order.lines.unlink()
			order['user_id'] = pos_order.user_id.id
			pos_order.write(self._order_fields(order))

		pos_order = pos_order.with_company(pos_order.company_id)
		self = self.with_company(pos_order.company_id)
		self._process_payment_lines(order, pos_order, pos_session, draft)

		if not draft:
			try:
				pos_order.action_pos_order_paid()
			except psycopg2.DatabaseError:
				# do not hide transactional errors, the order(s) won't be saved!
				raise
			except Exception as e:
				_logger.error('Could not fully process the POS Order: %s', tools.ustr(e))
			pos_order._create_order_picking()
			pos_order._compute_total_cost_in_real_time()

		if pos_order.to_invoice and pos_order.state == 'paid':
			pos_order._generate_pos_order_invoice()
			if pos_order.discount_on == 'orderlines':
				invoice = pos_order.account_move
				for line in invoice.invoice_line_ids:
					pos_line = line.pos_order_line_id
					if pos_line and pos_line.orderline_discount_type == "fixed":
						line.write({'price_unit': pos_line.price_unit})
				

		return pos_order.id

	def _prepare_invoice_vals(self):
		res = super(PosOrderInherit, self)._prepare_invoice_vals()
		res.update({
				'pos_order_id' : self.id,
				'order_discount': (self.order_discount),
				'is_created_from_pos' : True,
				'discount_on' : self.discount_on,
			})

		if self.order_discount > 0 :
			disc_line = self._prepare_discount_invoice_line()
			inv_lines = res.get('invoice_line_ids')
			inv_lines.append((0, None, disc_line))
			res.update({
				'invoice_line_ids' : inv_lines,
			}) 
		return res

	def _prepare_invoice_line(self, order_line):
		res = super(PosOrderInherit, self)._prepare_invoice_line(order_line)
		res.update({
			'pos_order_id' : self.id,
			'pos_order_line_id' : order_line.id,
			'orderline_discount_type' : order_line.orderline_discount_type ,
			'is_created_from_pos' : True,
		})
		return res