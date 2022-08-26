# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT

class PosConfigInherit(models.Model):
	_inherit = 'pos.config'
	
	allow_order_disc = fields.Boolean('Allow Order Discount')
	order_discount_on  = fields.Selection([('taxed', "Taxed Amount"), ('untaxed', "Untaxed Amount")], string='Order Discount On', default='taxed')
	acc_account_id = fields.Many2one('account.account', 'Discount Account',domain=[('user_type_id.name','=','Expenses'), ('discount_account','=',True)])
	disc_product_id = fields.Many2one("product.product",string="Discount Product", domain = [('type', '=', 'service'),('available_in_pos', '=', True)])

    

class AccountInherit(models.Model):
    _inherit = 'account.account'
    
    discount_account = fields.Boolean('Discount Account')