from odoo import fields, models, api, _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_is_zero
from odoo.exceptions import ValidationError
import pytz

import os
import time
import tempfile
import logging
_logger = logging.getLogger('Stock Report')
from datetime import datetime, timedelta
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
try:
    import xlwt
    import xlsxwriter
    from xlwt.Utils import rowcol_to_cell
except ImportError:
    _logger.debug('Can not import xlsxwriter`.')
import base64


class daily_stock_report(models.TransientModel):
    _inherit = "daily.stock.report"

    def get_locations2(self):
        location_obj = self.env['stock.location']
        locations = location_obj
        if self.warehouse_ids:
            for w in self.warehouse_ids:
                if w.lot_stock_id.usage == 'internal':
                    locations += w.lot_stock_id
        else:
            if self.location_ids:
                locations += self.location_ids
            else:
                locations += location_obj.search([
                    ('usage', '=', 'internal'), '|', ('company_id', '=', self.company_id.id),
                    ('company_id', '=', False)], order='level asc')
        if self.report_by == 'detailed_report' and self.location_id:
            locations = self.location_id
        return locations

    def get_product_available2(self, product, from_date=False, to_date=False, location=False,
                              warehouse=False, compute_child=True):
        """ Function to return stock """
        locations = self.get_child_locations(location)
        date_str, date_values = False, False
        where = [tuple(locations.ids), tuple(locations.ids), tuple([product.id])]
        if from_date and to_date:
            date_str = "move.date::DATE>=%s and move.date::DATE<=%s"
            where.append(tuple([from_date]))
            where.append(tuple([to_date]))
            print("where1 ++++++++++++++++++++++++", where)
        elif from_date:
            date_str = "move.date::DATE>=%s"
            date_values = [from_date]
            print("+++++++++++++++++++++===date_str", date_str)
            print("+++++++++++++++++++++===date_values", date_values)
        elif to_date:
            date_str = "move.date::DATE<=%s"
            date_values = [to_date]
            print("+++++++++++++++++++++===date_str1", date_str)
            print("+++++++++++++++++++++===date_values1", date_values)

        if date_values:
            where.append(tuple(date_values))
            print("where ++++++++++++++++++++++++", where)

        self._cr.execute(
            '''select sum(product_qty), product_id, product_uom 
            from stock_move move
            INNER JOIN stock_picking picking ON (move.picking_id = picking.id)
            INNER JOIN stock_picking_type picking_type ON (picking.picking_type_id = picking_type.id)
            where move.location_id NOT IN %s
            and move.location_dest_id IN %s
            and product_id IN %s and move.state = 'done' 
            and move.picking_id is not null
            and move.inventory_id is null
            and move.origin_returned_move_id is null
            '''
            + (date_str and 'and ' + date_str + ' ' or '') + \
            ''' and picking_type.code = 'incoming'
            group by product_id, product_uom''', tuple(where))
        results_incoming_purchases = self._cr.fetchall()
        # print("results_incoming_purchases", results_incoming_purchases)

        self._cr.execute(
            '''select sum(product_qty), product_id, product_uom 
            from stock_move move
            INNER JOIN stock_picking picking ON (move.picking_id = picking.id)
            INNER JOIN stock_picking_type picking_type ON (picking.picking_type_id = picking_type.id)
            where move.location_id NOT IN %s
            and move.location_dest_id IN %s
            and product_id IN %s and move.state = 'done' 
            and move.picking_id is not null
            and move.inventory_id is null
            and move.origin_returned_move_id is not null
            '''
            + (date_str and 'and ' + date_str + ' ' or '') + \
            ''' and picking_type.code = 'incoming'
            group by product_id, product_uom''', tuple(where))
        results_incoming_returns = self._cr.fetchall()
        # print("result incomming return", results_incoming_returns)

        self._cr.execute(
            '''select sum(product_qty), product_id, product_uom 
            from stock_move move 
            INNER JOIN stock_picking picking ON (move.picking_id = picking.id)
            INNER JOIN stock_picking_type picking_type ON (picking.picking_type_id = picking_type.id)
            where move.location_id IN %s
            and move.location_dest_id NOT IN %s
            and product_id IN %s and move.state = 'done' 
            and move.picking_id is not null
            and move.inventory_id is null
            '''
            + (date_str and 'and ' + date_str + ' ' or '') + \
            ''' and picking_type.code = 'outgoing'
            group by product_id, product_uom''', tuple(where))
        results_outgoing = self._cr.fetchall()
        # print("results_outgoing", results_outgoing)

        self._cr.execute(
            '''select sum(product_qty), product_id, product_uom 
            from stock_move move 
            INNER JOIN stock_picking picking ON (move.picking_id = picking.id)
            INNER JOIN stock_picking_type picking_type ON (picking.picking_type_id = picking_type.id)
            where move.location_id NOT IN %s
            and move.location_dest_id IN %s
            and product_id IN %s and move.state = 'done' 
            and move.picking_id is not null
            and move.inventory_id is null
            '''
            + (date_str and 'and ' + date_str + ' ' or '') + \
            ''' and picking_type.code = 'internal'
            group by product_id, product_uom''', tuple(where))
        results_internal_in = self._cr.fetchall()
        # print("results_internal_in", results_internal_in)

        self._cr.execute(
            '''select sum(product_qty), product_id, product_uom 
            from stock_move move 
            INNER JOIN stock_picking picking ON (move.picking_id = picking.id)
            INNER JOIN stock_picking_type picking_type ON (picking.picking_type_id = picking_type.id)
            where move.location_id IN %s
            and move.location_dest_id NOT IN %s
            and product_id IN %s and move.state = 'done' 
            and move.picking_id is not null
            and move.inventory_id is null
            '''
            + (date_str and 'and ' + date_str + ' ' or '') + \
            ''' and picking_type.code = 'internal'
            group by product_id, product_uom''', tuple(where))
        results_internal_out = self._cr.fetchall()
        # print("results_internal_out", results_internal_out)

        self._cr.execute(
            '''select sum(product_qty), product_id, product_uom 
            from stock_move move 
            where move.location_id NOT IN %s
            and move.location_dest_id IN %s
            and product_id IN %s and move.state = 'done' 
            and move.picking_id is null
            and move.inventory_id is not null
            '''
            + (date_str and 'and ' + date_str + ' ' or '') + \
            '''
            group by product_id, product_uom''', tuple(where))
        results_adjustment_in = self._cr.fetchall()
        # print("results_adjustment_in", results_adjustment_in)

        self._cr.execute(
            '''select sum(product_qty), product_id, product_uom 
            from stock_move move 
            where move.location_id IN %s
            and move.location_dest_id NOT IN %s
            and product_id IN %s and move.state = 'done' 
            and move.picking_id is null
            and move.inventory_id is not null
            '''  + (date_str and 'and ' + date_str + ' ' or '') + \
            ''' group by product_id, product_uom''', tuple(where))
        results_adjustment_out = self._cr.fetchall()
        # print("results_adjustment_out", results_adjustment_out)

        self._cr.execute(
            '''select sum(product_qty), product_id, product_uom 
            from stock_move move 
            where move.location_id NOT IN %s
            and move.location_dest_id IN %s
            and product_id IN %s and move.state = 'done' 
            and move.picking_id is null
            and move.inventory_id is null
            '''
            + (date_str and 'and ' + date_str + ' ' or '') + \
            '''
            group by product_id, product_uom''', tuple(where))
        results_production_in = self._cr.fetchall()
        # print("results_production_in", results_production_in)

        self._cr.execute(
            '''select sum(product_qty), product_id, product_uom 
            from stock_move move 
            where move.location_id IN %s
            and move.location_dest_id NOT IN %s
            and product_id IN %s and move.state = 'done' 
            and move.picking_id is null
            and move.inventory_id is null
            ''' + (date_str and 'and ' + date_str + ' ' or '') + \
            ''' group by product_id, product_uom''', tuple(where))
        results_production_out = self._cr.fetchall()
        # print("results_production_out", results_production_out)

        incoming_purchases, incoming_returns, outgoing, internal, adjustment, production = 0, 0, 0, 0, 0, 0
        # Count the quantities
        for quantity, prod_id, prod_uom in results_incoming_purchases:
            incoming_purchases += quantity
        for quantity, prod_id, prod_uom in results_incoming_returns:
            incoming_returns += quantity
        for quantity, prod_id, prod_uom in results_outgoing:
            outgoing += quantity
        for quantity, prod_id, prod_uom in results_internal_in:
            internal += quantity
        for quantity, prod_id, prod_uom in results_internal_out:
            internal -= quantity
        for quantity, prod_id, prod_uom in results_adjustment_in:
            adjustment += quantity
        for quantity, prod_id, prod_uom in results_adjustment_out:
            adjustment -= quantity
        for quantity, prod_id, prod_uom in results_production_in:
            production += quantity
        for quantity, prod_id, prod_uom in results_production_out:
            production -= quantity
        return {
            'incoming_purchases': incoming_purchases,
            'incoming_returns': incoming_returns,
            'outgoing': outgoing,
            'internal': internal,
            'adjustment': adjustment,
            'production': production,
            'balance': incoming_purchases + incoming_returns - outgoing + internal + adjustment + production
        }

    def category_summary_report(self):
        product_obj = self.env['product.product']
        end_date = datetime(self.to_date.year, self.to_date.month, self.to_date.day) + timedelta(hours=23, minutes=59, seconds=59)
        print("End Date", end_date)
        from_date = False
        if self.from_date:
            from_date = datetime(self.from_date.year, self.from_date.month, self.from_date.day, 0, 0, 0)
        print('from_date....', from_date)
        temp_dir = tempfile.gettempdir() or '/tmp'
        f_name = os.path.join(temp_dir, 'inventory_report.xlsx')
        workbook = xlsxwriter.Workbook(f_name)
        date_format = workbook.add_format({'num_format': 'd-m-yyyy',
                                           'align': 'center',
                                           'valign': 'vcenter'})
        # Styles
        style_header = workbook.add_format({
            'bold': 1,
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'})
        style_data = workbook.add_format({
            'bold': 1,
            'align': 'left'})
        style_data2 = workbook.add_format({
            'border': 1,
            'align': 'right'})
        style_data3 = workbook.add_format({
            'border': 1,
            'align': 'left'})
        style_total = workbook.add_format({
            'bold': 1,
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'})
        style_header2 = workbook.add_format({
            'bold': 1,
            'align': 'center',
            'valign': 'vcenter'})
        style_header.set_font_size(18)
        style_header.set_text_wrap()
        style_header.set_bg_color('428276') #('#d7e4bd')
        style_header.set_font_name('Tahoma')
        style_header.set_border(style=2)
        style_data.set_font_size(12)
        style_data.set_text_wrap()
        style_data.set_font_name('Tahoma')
        style_data.set_bg_color('b0d2d9')
        style_data2.set_font_size(12)
        style_data2.set_font_name('Tahoma')
        style_data3.set_font_size(12)
        style_data3.set_font_name('Tahoma')
        style_total.set_font_size(12)
        style_total.set_text_wrap()
        style_total.set_border(style=2)
        # date_format.set_font_size(12)
        # date_format.set_bg_color('#d7e4bd')
        date_format.set_font_name('Tahoma')
        date_format.set_border(style=1)
        style_header2.set_font_size(12)
        style_header2.set_bg_color('3f90a1') #('#d7e4bd')
        style_header2.set_font_name('Tahoma')
        style_header2.set_border(style=2)
        style_header2.set_text_wrap()
        worksheet = workbook.add_worksheet('Stock Report')
        worksheet.set_column(0, 0, 60)
        worksheet.set_column(1, 1, 25)
        worksheet.set_column(2, 2, 15)
        worksheet.set_column(3, 3, 15)

        worksheet.set_row(0, 25)
        worksheet.set_row(1, 25)
        worksheet.set_row(2, 40)
        row, col = 0, 0
        worksheet.merge_range(row, col, row, col + 1, self.company_id and self.company_id.name or '', style_header)
        row += 1
        worksheet.merge_range(row, col, row, col + 1, "Inventory Report", style_header)
        row += 1
        warehouse_name = ", ".join([w.name for w in self.warehouse_ids])
        worksheet.merge_range(row, col, row, col + 1, 'Warehouse:  ' + str(warehouse_name or ''), style_header2)
        row += 1
        worksheet.write(row, col, 'Date From', style_header2)
        if self.from_date:
            worksheet.write_datetime(row + 1, col, self.from_date or ' ', date_format)
        worksheet.write(row, col + 1, 'Date To', style_header2)
        worksheet.write(row + 1, col + 1, self.to_date or ' ', date_format)
        row += 2
        col = 0
        worksheet.write(row, col, 'Product', style_header2)
        worksheet.write(row, col + 1, 'Closing', style_header2)
        if self.show_valuation:
            worksheet.write(row, col + 2, 'Average Cost', style_header2)
            worksheet.write(row, col + 3, 'Valuation', style_header2)
        # worksheet.write(row, col + 2, 'Average Cost', style_header2)
        # if self.show_valuation:
        #     worksheet.write(row, col + 3, 'Valuation', style_header2)
        row += 1
        col = 0
        locations = self.get_locations2()
        locations = self.env['stock.location'].browse(list(set(locations.ids)))
        # locations = locations.sorted(lambda l: l.level)
        all_locations = self.get_child_locations(locations)
        # print('all_locations...', all_locations)
        products = product_obj.search([])
        categories = products.mapped('categ_id')
        price_prec = self.env['decimal.precision'].precision_get('Product Price')
        for categ in categories:
            worksheet.write(row, col, categ.complete_name, style_data)
            worksheet.write(row, col + 1, '', style_data)
            if self.show_valuation:
                worksheet.write(row, col + 2, '', style_data)
                worksheet.write(row, col + 3, '', style_data)
            row += 1
            found_product = False
            for product in products.filtered(lambda x: x.categ_id.id == categ.id):
                inv_dict = self.get_product_available(product, from_date=from_date, to_date=end_date, location=locations)
                qty_available = inv_dict.get('balance', 0.0)
                # print('product...qty_available...', product, qty_available)
                if self.skip_zero_stock:
                    if qty_available != 0.0:
                        worksheet.write(row, col, product.name, style_data3)
                        worksheet.write(row, col + 1, qty_available, style_data2)
                        if self.show_valuation:
                            worksheet.write(row, col + 2, product.standard_price or 0, style_data2)
                            worksheet.write(row, col + 3, round(qty_available * product.standard_price, price_prec) or 0, style_data2)
                        row += 1
                        found_product = True
                else:
                    worksheet.write(row, col, product.name, style_data3)
                    worksheet.write(row, col + 1, qty_available, style_data2)
                    if self.show_valuation:
                        worksheet.write(row, col + 2, product.standard_price or 0, style_data2)
                        worksheet.write(row, col + 3, round(qty_available * product.standard_price, price_prec) or 0, style_data2)
                    row += 1
                    found_product = True
            if not found_product:
                row -= 1
        workbook.close()
        f = open(f_name, 'rb')
        data = f.read()
        f.close()
        name = "%s.xlsx" % ("InventoryReport_" + str(self.from_date or '') + '_' + str(self.to_date or ''))
        out_wizard = self.env['xlsx.output'].create({'name': name,
                                                     'xls_output': base64.encodebytes(data)})
        view_id = self.env.ref('gts_stock_xlsx_report.xlsx_output_form').id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'xlsx.output',
            'target': 'new',
            'view_mode': 'form',
            'res_id': out_wizard.id,
            'views': [[view_id, 'form']],
        }
