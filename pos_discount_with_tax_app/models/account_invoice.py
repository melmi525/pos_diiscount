# -*- coding: utf-8 -*-
import logging
from datetime import timedelta
import psycopg2
import pytz
from odoo import api, fields, models, tools, _
from odoo.tools import float_is_zero
from odoo.exceptions import UserError
from odoo.http import request
import odoo.addons.decimal_precision as dp


_logger = logging.getLogger(__name__)

class AccountInvoiceInherit(models.Model):
	_inherit = "account.move"

	pos_order_id = fields.Many2one('pos.order',string="POS order" ,readonly=True)
	order_discount = fields.Float("Discount",default=0.0 ,readonly=True)
	is_created_from_pos = fields.Boolean("Is Created From POS" ,readonly=True)
	discount_on = fields.Char('Discount On' ,readonly=True)

	

	def _recompute_tax_lines(self, recompute_tax_base_amount=False):
		""" Compute the dynamic tax lines of the journal entry.

		:param recompute_tax_base_amount: Flag forcing only the recomputation of the `tax_base_amount` field.
		"""
		self.ensure_one()
		in_draft_mode = self != self._origin

		def _serialize_tax_grouping_key(grouping_dict):
			''' Serialize the dictionary values to be used in the taxes_map.
			:param grouping_dict: The values returned by '_get_tax_grouping_key_from_tax_line' or '_get_tax_grouping_key_from_base_line'.
			:return: A string representing the values.
			'''
			return '-'.join(str(v) for v in grouping_dict.values())

		def _compute_base_line_taxes(base_line):
			''' Compute taxes amounts both in company currency / foreign currency as the ratio between
			amount_currency & balance could not be the same as the expected currency rate.
			The 'amount_currency' value will be set on compute_all(...)['taxes'] in multi-currency.
			:param base_line:   The account.move.line owning the taxes.
			:return:            The result of the compute_all method.
			'''
			move = base_line.move_id

			if move.is_invoice(include_receipts=True):
				handle_price_include = True
				sign = -1 if move.is_inbound() else 1
				quantity = base_line.quantity
				is_refund = move.move_type in ('out_refund', 'in_refund')
				line_discount = base_line.price_unit * (1 - (base_line.discount / 100.0))
				if base_line.pos_order_id.discount_on == 'orderline':
					if base_line.pos_order_id and base_line.orderline_discount_type == "fixed":
						line_discount = base_line.price_unit - base_line.discount
				
				price_unit_wo_discount = sign * line_discount
			else:
				handle_price_include = False
				quantity = 1.0
				tax_type = base_line.tax_ids[0].type_tax_use if base_line.tax_ids else None
				is_refund = (tax_type == 'sale' and base_line.debit) or (tax_type == 'purchase' and base_line.credit)
				price_unit_wo_discount = base_line.amount_currency

			return base_line.tax_ids._origin.with_context(force_sign=move._get_tax_force_sign()).compute_all(
				price_unit_wo_discount,
				currency=base_line.currency_id,
				quantity=quantity,
				product=base_line.product_id,
				partner=base_line.partner_id,
				is_refund=is_refund,
				handle_price_include=handle_price_include,
				include_caba_tags=move.always_tax_exigible,
			)
		taxes_map = {}

		# ==== Add tax lines ====
		to_remove = self.env['account.move.line']
		for line in self.line_ids.filtered('tax_repartition_line_id'):
			grouping_dict = self._get_tax_grouping_key_from_tax_line(line)
			grouping_key = _serialize_tax_grouping_key(grouping_dict)
			if grouping_key in taxes_map:
				# A line with the same key does already exist, we only need one
				# to modify it; we have to drop this one.
				to_remove += line
			else:
				taxes_map[grouping_key] = {
					'tax_line': line,
					'amount': 0.0,
					'tax_base_amount': 0.0,
					'grouping_dict': False,
				}
		if not recompute_tax_base_amount:
			self.line_ids -= to_remove

		# ==== Mount base lines ====
		xyz = self.line_ids.filtered(lambda line: not line.tax_repartition_line_id)
		for line in self.line_ids.filtered(lambda line: not line.tax_repartition_line_id):
			# Don't call compute_all if there is no tax.
			if not line.tax_ids:
				if not recompute_tax_base_amount:
					line.tax_tag_ids = [(5, 0, 0)]
				continue
			compute_all_vals = _compute_base_line_taxes(line)

			# Assign tags on base line
			if not recompute_tax_base_amount:
				line.tax_tag_ids = compute_all_vals['base_tags'] or [(5, 0, 0)]

			for tax_vals in compute_all_vals['taxes']:
				grouping_dict = self._get_tax_grouping_key_from_base_line(line, tax_vals)
				grouping_key = _serialize_tax_grouping_key(grouping_dict)

				tax_repartition_line = self.env['account.tax.repartition.line'].browse(tax_vals['tax_repartition_line_id'])
				tax = tax_repartition_line.invoice_tax_id or tax_repartition_line.refund_tax_id

				taxes_map_entry = taxes_map.setdefault(grouping_key, {
					'tax_line': None,
					'amount': 0.0,
					'tax_base_amount': 0.0,
					'grouping_dict': False,
				})
				taxes_map_entry['amount'] += tax_vals['amount']
				taxes_map_entry['tax_base_amount'] += self._get_base_amount_to_display(tax_vals['base'], tax_repartition_line, tax_vals['group'])
				taxes_map_entry['grouping_dict'] = grouping_dict

		# ==== Pre-process taxes_map ====
		taxes_map = self._preprocess_taxes_map(taxes_map)

		# ==== Process taxes_map ====
		for taxes_map_entry in taxes_map.values():
			# The tax line is no longer used in any base lines, drop it.
			if taxes_map_entry['tax_line'] and not taxes_map_entry['grouping_dict']:
				if not recompute_tax_base_amount:
					self.line_ids -= taxes_map_entry['tax_line']
				continue

			currency = self.env['res.currency'].browse(taxes_map_entry['grouping_dict']['currency_id'])

			# tax_base_amount field is expressed using the company currency.
			tax_base_amount = currency._convert(taxes_map_entry['tax_base_amount'], self.company_currency_id, self.company_id, self.date or fields.Date.context_today(self))

			# Recompute only the tax_base_amount.
			if recompute_tax_base_amount:
				if taxes_map_entry['tax_line']:
					taxes_map_entry['tax_line'].tax_base_amount = tax_base_amount
				continue

			balance = currency._convert(
				taxes_map_entry['amount'],
				self.company_currency_id,
				self.company_id,
				self.date or fields.Date.context_today(self),
			)
			to_write_on_line = {
				'amount_currency': taxes_map_entry['amount'],
				'currency_id': taxes_map_entry['grouping_dict']['currency_id'],
				'debit': balance > 0.0 and balance or 0.0,
				'credit': balance < 0.0 and -balance or 0.0,
				'tax_base_amount': tax_base_amount,
			}

			if taxes_map_entry['tax_line']:
				# Update an existing tax line.
				taxes_map_entry['tax_line'].update(to_write_on_line)
			else:
				# Create a new tax line.
				create_method = in_draft_mode and self.env['account.move.line'].new or self.env['account.move.line'].create
				tax_repartition_line_id = taxes_map_entry['grouping_dict']['tax_repartition_line_id']
				tax_repartition_line = self.env['account.tax.repartition.line'].browse(tax_repartition_line_id)
				tax = tax_repartition_line.invoice_tax_id or tax_repartition_line.refund_tax_id
				taxes_map_entry['tax_line'] = create_method({
					**to_write_on_line,
					'name': tax.name,
					'move_id': self.id,
					'company_id': line.company_id.id,
					'company_currency_id': line.company_currency_id.id,
					'tax_base_amount': tax_base_amount,
					'exclude_from_invoice_tab': True,
					**taxes_map_entry['grouping_dict'],
				})

			if in_draft_mode:
				taxes_map_entry['tax_line'].update(taxes_map_entry['tax_line']._get_fields_onchange_balance(force_computation=True))




	


	def get_taxes_values(self):
		tax_grouped = {}
		round_curr = self.currency_id.round
		for line in self.invoice_line_ids:
			price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
			if line.orderline_discount_type  == "fixed":
				price_unit = line.price_unit  - line.discount 
			taxes = line.invoice_line_tax_ids.compute_all(price_unit, self.currency_id, line.quantity, line.product_id, self.partner_id)['taxes']
			for tax in taxes:
				val = self._prepare_tax_line_vals(line, tax)
				key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

				if key not in tax_grouped:
					tax_grouped[key] = val
					tax_grouped[key]['base'] = round_curr(val['base'])
				else:
					tax_grouped[key]['amount'] += val['amount']
					tax_grouped[key]['base'] += round_curr(val['base'])
		return tax_grouped

	@api.depends(
	'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
	'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
	'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
	'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
	'line_ids.debit',
	'line_ids.credit',
	'line_ids.currency_id',
	'line_ids.amount_currency',
	'line_ids.amount_residual',
	'line_ids.amount_residual_currency',
	'line_ids.payment_id.state',
	'line_ids.full_reconcile_id')
	def _compute_amount(self):
		for move in self:

			if move.payment_state == 'invoicing_legacy':
				# invoicing_legacy state is set via SQL when setting setting field
				# invoicing_switch_threshold (defined in account_accountant).
				# The only way of going out of this state is through this setting,
				# so we don't recompute it here.
				move.payment_state = move.payment_state
				continue

			total_untaxed = 0.0
			total_untaxed_currency = 0.0
			total_tax = 0.0
			total_tax_currency = 0.0
			total_to_pay = 0.0
			total_residual = 0.0
			total_residual_currency = 0.0
			total = 0.0
			total_currency = 0.0
			currencies = set()

			for line in move.line_ids:
				if line.currency_id:
					currencies.add(line.currency_id)

				if move.is_invoice(include_receipts=True):
					# === Invoices ===

					if not line.exclude_from_invoice_tab:
						# Untaxed amount.
						total_untaxed += line.balance
						total_untaxed_currency += line.amount_currency
						total += line.balance
						total_currency += line.amount_currency
					elif line.tax_line_id:
						# Tax amount.
						total_tax += line.balance
						total_tax_currency += line.amount_currency
						total += line.balance
						total_currency += line.amount_currency
					elif line.account_id.user_type_id.type in ('receivable', 'payable'):
						# Residual amount.
						total_to_pay += line.balance
						total_residual += line.amount_residual
						total_residual_currency += line.amount_residual_currency
				else:
					# === Miscellaneous journal entry ===
					if line.debit:
						total += line.balance
						total_currency += line.amount_currency

			if move.move_type == 'entry' or move.is_outbound():
				sign = 1
			else:
				sign = -1
			move.amount_untaxed = sign * (total_untaxed_currency if len(currencies) == 1 else total_untaxed)
			move.amount_tax = sign * (total_tax_currency if len(currencies) == 1 else total_tax)
			move.amount_total = sign * (total_currency if len(currencies) == 1 else total)
			move.amount_residual = -sign * (total_residual_currency if len(currencies) == 1 else total_residual)
			move.amount_untaxed_signed = -total_untaxed
			move.amount_tax_signed = -total_tax
			move.amount_total_signed = abs(total) if move.move_type == 'entry' else -total
			move.amount_residual_signed = total_residual

			currency = len(currencies) == 1 and currencies.pop() or move.company_id.currency_id

			# Compute 'payment_state'.
			new_pmt_state = 'not_paid' if move.move_type != 'entry' else False

			if move.is_invoice(include_receipts=True) and move.state == 'posted':

				if currency.is_zero(move.amount_residual):
					if all(payment.is_matched for payment in move._get_reconciled_payments()):
						new_pmt_state = 'paid'
					else:
						new_pmt_state = move._get_invoice_in_payment_state()
				elif currency.compare_amounts(total_to_pay, total_residual) != 0:
					new_pmt_state = 'partial'

			if new_pmt_state == 'paid' and move.move_type in ('in_invoice', 'out_invoice', 'entry'):
				reverse_type = move.move_type == 'in_invoice' and 'in_refund' or move.move_type == 'out_invoice' and 'out_refund' or 'entry'
				reverse_moves = self.env['account.move'].search([('reversed_entry_id', '=', move.id), ('state', '=', 'posted'), ('move_type', '=', reverse_type)])

				# We only set 'reversed' state in cas of 1 to 1 full reconciliation with a reverse entry; otherwise, we use the regular 'paid' state
				reverse_moves_full_recs = reverse_moves.mapped('line_ids.full_reconcile_id')
				if reverse_moves_full_recs.mapped('reconciled_line_ids.move_id').filtered(lambda x: x not in (reverse_moves + reverse_moves_full_recs.mapped('exchange_move_id'))) == move:
					new_pmt_state = 'reversed'

			move.payment_state = new_pmt_state


class AccountInvoiceLineInherit(models.Model):
	_inherit = "account.move.line"

	pos_order_id = fields.Many2one('pos.order',string="POS order" ,readonly=True)
	pos_order_line_id = fields.Many2one('pos.order.line',string="POS order Line" ,readonly=True)
	orderline_discount_type = fields.Char('Discount Type' ,readonly=True)
	is_created_from_pos = fields.Boolean("Is Created From POS" ,readonly=True)

	


	
			
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:   