# -*- coding: utf-8 -*-
# -*- encoding: utf-8 -*-

#############################################################################
#
#    Copyright (c) 2007 Martin Reisenhofer <martin.reisenhofer@funkring.net>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import osv
from openerp.tools.translate import _


class account_invoice(osv.osv):
    
    def _calc_product_commission(self,cr,uid,ids,context=None):
        commission_obj = self.pool.get("at_commission_product.commission")
        invoice_obj = self.pool.get("account.invoice")      
        commission_line_obj = self.pool.get("at_commission.line")        
        period_obj = self.pool.get("account.period")
        for invoice in self.browse(cr, uid, ids, context=context):
            """ Create Analytic lines for invoice """          
            company = invoice.company_id
            #
            if company.commission_type == "invoice" or invoice.type in ("out_refund","in_invoice"):
                if invoice.type in ("out_invoice", "in_refund"):       
                    sign = 1
                else:
                    sign = -1                
                #            
                for line in invoice.invoice_line:
                    product = line.product_id
                    analytic_account = line.account_analytic_id
                    if analytic_account and product:
                        commission_ids = commission_obj.search(cr,uid,[("product_id","=",product.id)])                    
                        if commission_ids:
                            ref = invoice_obj.invoice_ref(cr,uid,invoice)
                            #
                            orders = [l.order_id for l in line.sale_order_line_ids]                            
                            order_names = [o.name for o in orders]                            
                            order_date =   min([o.date_order for o in orders])
                            order_period_id = period_obj.find_period_id(cr,uid,order_date)
                            price_subtotal = line.price_subtotal*sign
                            #
                            period_id = order_period_id or invoice.period_id.id
                            commission_date = order_date or invoice.date_invoice                            
                            #
                            for commission in commission_obj.browse(cr,uid,commission_ids):
                                commission_product = commission.property_commission_product
                                percent = commission.commission_percent
                                if percent:
                                    #
                                    factor = percent / 100.0
                                    amount = price_subtotal * factor
                                    #
                                    values = {
                                        "name": _("Product Commission: %s") % (line.name,),
                                        "date": commission_date,
                                        "invoice_id" : invoice.id,
                                        "account_id": analytic_account.id,
                                        "unit_amount": line.quantity,
                                        "amount": amount,
                                        "base_commission" : percent,
                                        "total_commission" : percent,
                                        "product_id": commission_product.id,
                                        "product_uom_id": commission_product.uom_id.id,
                                        "general_account_id": commission_product.account_income_standard_id.id,
                                        "journal_id": commission.property_analytic_journal.id,
                                        "partner_id" : commission.partner_id.id,
                                        "invoice_line_id" : line.id,
                                        "user_id" : uid,
                                        "ref": ":".join(order_names) or ref or None,
                                        "sale_partner_id" : invoice.partner_id.id,
                                        "sale_product_id" : line.product_id.id,
                                        "period_id" : period_id,
                                        "price_sub" : price_subtotal,
                                    }
                                    commission_line_ids = commission_line_obj.search(cr, uid, [("invoice_line_id", "=", line.id), ("partner_id", "=", commission.partner_id.id)])
                                    commission_line_id = commission_line_ids and commission_line_ids[0] or None
                                    #
                                    if not commission_line_id:
                                        commission_line_obj.create(cr, uid, values)                                        
                                    elif commission_line_id and not commission_line_obj.browse(cr, uid, commission_line_id).invoiced_id:
                                        commission_line_obj.write(cr, uid, commission_line_id, values)    
    
    def action_move_create(self, cr, uid, ids, *args):
        super(account_invoice,self).action_move_create(cr, uid, ids, *args)
        self._calc_product_commission(cr,uid,ids)
        
    _inherit = "account.invoice"
account_invoice()
