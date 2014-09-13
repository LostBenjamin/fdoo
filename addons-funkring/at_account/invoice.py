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

import time
from openerp.osv import osv,fields
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class account_invoice(osv.osv):


    def _create_payment(self, cr, uid, invoice_id, journal_id, 
                        compensation_id=None, 
                        amount=0.0, 
                        date=None, 
                        voucher_id=None, 
                        post=False, 
                        currency_id=None,
                        period_id=None,
                        context=None):
        
        res_value = {}
        if not invoice_id or not journal_id:
            return res_value
        
        voucher_obj = self.pool.get("account.voucher")
        voucher_line_obj = self.pool.get("account.voucher.line")
        compensation_obj = self.pool.get("account.bank.statement.compensation")
        partner_obj = self.pool.get("res.partner")
        move_line_obj = self.pool.get("account.move.line")
        period_obj = self.pool.get("account.period")
        
        invoice = self.browse(cr, uid, invoice_id, context=context)        
        currency = invoice.currency_id
        invoice_journal = invoice.journal_id
        company = invoice.company_id
        residual_amount = invoice.type in ("out_refund", "in_refund") and -invoice.residual or invoice.residual
        payment_rate = 1.0
        payment_rate_currency = currency_id and self.pool["res.currency"].browse(cr, uid, currency_id, context=context) or currency
        voucher_type = invoice.type in ("out_invoice","out_refund") and "receipt" or "payment"
        account_type = voucher_type == "payment" and "payable" or "receivable"
        partner = partner_obj._find_accounting_partner(invoice.partner_id)

        if not amount:
            amount = residual_amount
            
        if not period_id:
            period_ids = period_obj.find(cr, uid, dt=(date or util.currentDate()), context=context)
            if period_ids:
                period_id = period_ids[0]

        voucher_context = dict(context) or {}
        voucher_context["payment_expected_currency"]=invoice.currency_id.id
        voucher_context["default_partner_id"]=partner.id
        voucher_context["default_amount"]= amount
        voucher_context["default_is_multi_currency"]=False
        voucher_context["default_type"]=voucher_type
        voucher_context["search_disable_custom_filters"]=True
        voucher_context["type"]= voucher_type
        voucher_context["invoice_id"]=invoice.id
        voucher_context["journal_id"]=journal_id
        voucher_context["period_id"]=period_id

        #get move_lines from invoice
        #move_lines_ids = move_line_obj.search(cr, uid, [("move_id","=",invoice.move_id.id),("state","=","valid"), ("account_id.type", "=", account_type), ("reconcile_id", "=", False), ("partner_id", "=", partner.id)], context=context)
        #voucher_context["move_line_ids"]=move_lines_ids

        #test if voucher is valid for invoice
        if voucher_id:
            voucher = voucher_obj.browse(cr,uid,voucher_id,context=context)
            voucher_line_obj.unlink(cr,uid,[l.id for l in voucher.line_ids])
            invoice_valid = False
            for voucher_invoice in voucher.invoice_ids:
                if voucher_invoice.id == invoice_id:
                    invoice_valid = True
                    break

            if not invoice_valid:
                voucher_obj.unlink(cr, uid, [voucher_id], context=context)
                voucher_id = None

        data = { "payment_option" : "without_writeoff",
                 "comment" : _("Write-Off"),
                 "journal_id" : journal_id }

        if date:
            data["date"]=date

        data.update(voucher_obj.onchange_amount(cr, uid, [], amount, payment_rate,
                                   partner.id, None, currency.id, voucher_type, date,
                                   payment_rate_currency.id, company.id, context=voucher_context)["value"])

        data.update(voucher_obj.onchange_journal(cr, uid, [], journal_id, [],
                                  False, invoice.partner_id.id, date, residual_amount, voucher_type, company.id, context=voucher_context)["value"])

        if voucher_type == "receipt":
            line_datas_field = "line_cr_ids"
            line_datas = data.get("line_cr_ids",[])
            data.pop("line_dr_ids",None)
            sign=1.0
        else:
            line_datas_field = "line_dr_ids"
            line_datas = data.get("line_dr_ids",[])
            data.pop("line_cr_ids",None)
            sign=-1.0

        if len(line_datas) == 1:
             line_datas[0]["amount"]=amount
             # compensation
             if compensation_id:
                 compensation = compensation_obj.browse(cr,uid,compensation_id,context=context)
                 data["payment_option"]="with_writeoff"
                 data["writeoff_acc_id"]=compensation.account_id.id
                 data["comment"]=compensation.name
           

        if line_datas:
            data[line_datas_field] = [(0,0,l) for l in line_datas]

        #if no voucher id exist create one
        if not voucher_id:
            voucher_id = voucher_obj.create(cr,uid,data,voucher_context)
        else:
            voucher_obj.write(cr,uid,voucher_id,data,voucher_context)

        # result
        voucher = voucher_obj.browse(cr,uid,voucher_id,context=context)
        res_value["voucher_id"]=voucher_id
        res_value["invoice_id"]=invoice_id
        res_value["account_id"]=invoice.account_id.id
        res_value["partner_id"]=invoice.partner_id.id
        res_value["amount"]=amount*sign
        res_value["residual_amount"]=voucher.writeoff_amount

        #if not name:
        res_value["name"]=invoice.move_id.name
        #if not ref:
        res_value["ref"]=invoice.reference

        #type
        if invoice_journal.type == "sale":
            res_value["type"] = "customer"
        elif invoice_journal.type == "purchase":
            res_value["type"] = "supplier"
        else:
            res_value["type"] = "general"
            
        # post voucher
        if post:
            voucher_obj.proforma_voucher(cr, uid, voucher_id, context=voucher_context)

        return res_value
        

    def invoice_validate(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'open'}, context=context)

        attachment_obj = self.pool.get("ir.attachment")
        attachment_wizard_obj  = self.pool.get("account.invoice.attachment.wizard")

        # reimport first attachment as receipt if it is an pdf
        invoice_ids = self.search(cr, uid, [("id","in",ids),("type","in",["in_invoice","in_refund"])])
        for oid in invoice_ids:
            attachment_ids = attachment_obj.search(cr, uid, [("res_model","=","account.invoice"),("res_id","=",oid)])
            if len(attachment_ids) == 1:
                # get attachment
                attachment = attachment_obj.browse(cr, uid, attachment_ids[0], context=context)
                if attachment.origin != "account.invoice.attachment.wizard" and attachment.name and attachment.name.lower().endswith(".pdf"):
                    attachment_data = attachment.datas
                    if attachment_data:
                        # import attachment
                        wizard_context = context and dict(context) or {}
                        wizard_context["active_model"]="account.invoice"
                        wizard_context["active_ids"]=[oid]
                        wizard_id = attachment_wizard_obj.create(cr, uid, { "document" : attachment_data }, context=wizard_context )
                        attachment_wizard_obj.action_import(cr, uid, [wizard_id], context=wizard_context)
                        # clean up
                        attachment.unlink()
                        attachment_wizard_obj.unlink(cr, uid, [wizard_id])



        return True

    def _tax_amount(self,cr,uid,sid,context=None):
        """
        RETURN: {
                tax.id: 0.0
            }
        """
        res = {}
        invoice_rec = self.browse(cr, uid, sid, context)
        for line_rec in invoice_rec.invoice_line:
            tax_calc = self.pool.get("account.tax").compute_all(cr, uid, line_rec.invoice_line_tax_id, line_rec.price_unit * (1-(line_rec.discount or 0.0)/100.0), line_rec.quantity, line_rec.product_id.id, line_rec.invoice_id.partner_id.id)
            for tax in tax_calc["taxes"]:
                tax_id = tax["id"]
                tax_amount = tax.get("amount",0.0)
                amount = res.get(tax_id,0.0)
                amount += tax_amount
                res[tax_id] = amount
        return res

    def _invoice_text(self, cr, uid, ids, field_name, args, context=None):
        res = dict.fromkeys(ids)
        for invoice in self.browse(cr, uid, ids):
            if invoice.type == "out_invoice":
                res[invoice.id] = invoice.company_id.invoice_text
            elif invoice.type == "in_invoice":
                res[invoice.id] = invoice.company_id.invoice_in_text
            elif invoice.type == "out_refund":
                res[invoice.id] = invoice.company_id.refund_text
            elif invoice.type ==  "in_refund":
                res[invoice.id] = invoice.company_id.refund_in_text
        return res

    def _replace_invoice_ids_with_id(self, cr, uid, ids, oid, context=None):
        pass

    def invoice_ref(self,cr,uid,invoice):
        res = None
        if invoice.type in ("in_invoice", "in_refund"):
            res = invoice.reference
        else:
            res = self._convert_ref(cr, uid, invoice.number)
        if not res:
            res = invoice.name
        return res

    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if context is None:
            context = {}
        ids = []
        if name:
            ids = self.search(cr, user, [('number','=',name)] + args, limit=limit, context=context)
        if not ids:
            ids = self.search(cr, user, [('name',operator,name)] + args, limit=limit, context=context)
        if not ids:
            ids = self.search(cr, user, [('number',operator,name)] + args, limit=limit, context=context)
        if not ids:
            ids = self.search(cr, user, [('reference',operator,name)] + args, limit=limit, context=context)
        if not ids:
            ids = self.search(cr, user, [('partner_id',operator,name)] + args, limit=limit, context=context)
        return self.name_get(cr, user, ids, context)

    def _get_subject(self,cr,uid,ids,field_name,arg,context=None):
        res = dict.fromkeys(ids)
        for invoice in self.browse(cr, uid, ids, context):
            if invoice.type=='out_invoice' and (invoice.state=='open' or invoice.state=='paid'):
                res[invoice.id] = _("Invoice")
            elif invoice.type == 'out_invoice' and invoice.state == 'proforma2':
                res[invoice.id] =_("Pro-forma")
            elif invoice.type == 'out_invoice' and invoice.state == 'draft':
                res[invoice.id] = _("Proposal")
            elif invoice.type == 'out_invoice' and invoice.state == 'cancel':
                res[invoice.id] = _("Cancellation")
            elif invoice.type == 'out_refund':
                res[invoice.id] = _("Refund")
            elif invoice.type=='in_refund':
                res[invoice.id] = _("Supplier Refund")
            elif invoice.type=='in_invoice':
                res[invoice.id] = _("Supplier Invoice")
            else:
                res[invoice.id] = ''
        return res

    _inherit = "account.invoice"
    _columns = {
        "invoice_text" : fields.function(_invoice_text, type="text", string="Invoice Text"),
        "subject" : fields.function(_get_subject, type="char", size=128, string="Subject"),
    }


class account_invoice_line(osv.osv):

    def move_line_get(self, cr, uid, invoice_id, context=None):
        res = []
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        if context is None:
            context = {}
        inv = self.pool.get('account.invoice').browse(cr, uid, invoice_id, context=context)
        company_currency = self.pool['res.company'].browse(cr, uid, inv.company_id.id).currency_id.id
        for line in inv.invoice_line:
            mres = self.move_line_get_item(cr, uid, line, context)
            if not mres:
                continue
            res.append(mres)
            tax_code_found= False
            for tax in tax_obj.compute_all(cr, uid, line.invoice_line_tax_id,
                    (line.price_unit * (1.0 - (line['discount'] or 0.0) / 100.0)),
                    line.quantity, line.product_id,
                    inv.partner_id)['taxes']:

                if inv.type in ('out_invoice', 'in_invoice'):
                    if inv.type == "in_invoice":
                        tax_code_id = tax['ref_base_code_id']
                    else:
                        tax_code_id = tax['base_code_id']
                    tax_amount = line.price_subtotal * tax['base_sign']
                else:
                    if inv.type == "in_refund":
                        tax_code_id = tax['base_code_id']
                    else:
                        tax_code_id = tax['ref_base_code_id']
                    tax_amount = line.price_subtotal * tax['ref_base_sign']

                if tax_code_found:
                    if not tax_code_id:
                        continue
                    res.append(self.move_line_get_item(cr, uid, line, context))
                    res[-1]['price'] = 0.0
                    res[-1]['account_analytic_id'] = False
                elif not tax_code_id:
                    continue
                tax_code_found = True

                res[-1]['tax_code_id'] = tax_code_id
                res[-1]['tax_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, tax_amount, context={'date': inv.date_invoice})
        return res

    def _price_unit_untaxed(self, cr, uid, ids, field_name, arg, context=None):
        if context is None:
            context = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        res = dict.fromkeys(ids,0.0)
        for line in self.browse(cr, uid, ids, context=context):
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = tax_obj.compute_all(cr, uid, line.invoice_line_tax_id, price, 1, line.product_id.id, line.partner_id.id)
            cur = line.invoice_id.currency_id
            res[line.id] = cur_obj.round(cr, uid, cur, taxes['total'])
        return res

    def _amount_line_taxed(self, cr, uid, ids, field_name, arg, context=None):
        if context is None:
            context = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        res = dict.fromkeys(ids,0.0)
        for line in self.browse(cr, uid, ids, context=context):
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = tax_obj.compute_all(cr, uid, line.invoice_line_tax_id, price, line.quantity, line.product_id.id, line.partner_id.id)
            cur = line.invoice_id.currency_id
            res[line.id] = cur_obj.round(cr, uid, cur, taxes['total_included'])
        return res


    def _product_tax_ids(self, cr, uid, ids, field_name, arg, context=None):
        res = dict.fromkeys(ids)
        for obj in self.browse(cr, uid, ids, context):
            res[obj.id]=[]

            invoice = obj.invoice_id
            product = obj.product_id
            account = obj.account_id

            if invoice and product:
                taxes = None
                if invoice.type in ("out_invoice","out_refund"):
                    taxes = product.taxes_id or (account and account.tax_ids or False)
                else:
                    taxes = product.supplier_taxes_id or (account and account.tax_ids or False)
                res[obj.id] = (taxes and [x.id for x in taxes]) or []

        return res

    def _discount_amount(self, cr, uid, ids, field_name, arg, context=None):
        res=dict.fromkeys(ids,0)
        tax_obj = self.pool.get('account.tax')
        for line in self.browse(cr, uid, ids):
            if line.discount:
                price_with_discount = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                taxes_with_discount = tax_obj.compute_all(cr, uid, line.invoice_line_tax_id, price_with_discount, line.quantity, line.product_id.id, line.partner_id.id)
                taxes =  tax_obj.compute_all(cr, uid, line.invoice_line_tax_id,  line.price_unit, line.quantity, line.product_id.id, line.partner_id.id)
                res[line.id]= taxes["total"]-taxes_with_discount["total"]
        return res

    _inherit = "account.invoice.line"
    _columns = {
            "price_subtotal_taxed" : fields.function(_amount_line_taxed,string="Subtotal (Brutto)",digits_compute= dp.get_precision('Account')),
            "price_unit_untaxed" : fields.function(_price_unit_untaxed,string="Price Unit (Netto)",digits_compute= dp.get_precision('Account')),
            "product_tax_ids" : fields.function(_product_tax_ids,type="many2many",obj="account.tax",string="Product Taxes",help="Original Product Taxes without fiscal position"),
            "discount_amount" : fields.function(_discount_amount, type="float", string="Discount Amount", readonly=True),
            "note" : fields.text("Note")
    }


class account_invoice_tax(osv.osv):

    def compute(self, cr, uid, invoice_id, context=None):
        tax_grouped = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        inv = self.pool.get('account.invoice').browse(cr, uid, invoice_id.id, context=context)
        cur = inv.currency_id
        company_currency = self.pool['res.company'].browse(cr, uid, inv.company_id.id).currency_id.id
        for line in inv.invoice_line:
            for tax in tax_obj.compute_all(cr, uid, line.invoice_line_tax_id, (line.price_unit* (1-(line.discount or 0.0)/100.0)), line.quantity, line.product_id, inv.partner_id)['taxes']:
                val={}
                val['invoice_id'] = inv.id
                val['name'] = tax['name']
                val['amount'] = tax['amount']
                val['manual'] = False
                val['sequence'] = tax['sequence']
                val['base'] = cur_obj.round(cr, uid, cur, tax['price_unit'] * line['quantity'])

                if inv.type in ('out_invoice','in_invoice'):
                    if inv.type == "in_invoice":
                        val['base_code_id'] = tax['ref_base_code_id']
                        val['tax_code_id'] = tax['ref_tax_code_id']
                        val['account_id'] = tax['account_paid_id'] or line.account_id.id
                        val['account_analytic_id'] = tax['account_analytic_paid_id']
                    else:
                        val['base_code_id'] = tax['base_code_id']
                        val['tax_code_id'] = tax['tax_code_id']
                        val['account_id'] = tax['account_collected_id'] or line.account_id.id
                        val['account_analytic_id'] = tax['account_analytic_collected_id']

                    val['base_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['base'] * tax['base_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['tax_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['amount'] * tax['tax_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                else:
                    if inv.type == "in_refund":
                        val['base_code_id'] = tax['base_code_id']
                        val['tax_code_id'] = tax['tax_code_id']
                        val['account_id'] = tax['account_collected_id'] or line.account_id.id
                        val['account_analytic_id'] = tax['account_analytic_collected_id']
                    else:
                        val['base_code_id'] = tax['ref_base_code_id']
                        val['tax_code_id'] = tax['ref_tax_code_id']
                        val['account_id'] = tax['account_paid_id'] or line.account_id.id
                        val['account_analytic_id'] = tax['account_analytic_paid_id']

                    val['base_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['base'] * tax['ref_base_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['tax_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['amount'] * tax['ref_tax_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)

                key = (val['tax_code_id'], val['base_code_id'], val['account_id'], val['account_analytic_id'])
                if not key in tax_grouped:
                    tax_grouped[key] = val
                else:
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base'] += val['base']
                    tax_grouped[key]['base_amount'] += val['base_amount']
                    tax_grouped[key]['tax_amount'] += val['tax_amount']

        for t in tax_grouped.values():
            t['base'] = cur_obj.round(cr, uid, cur, t['base'])
            t['amount'] = cur_obj.round(cr, uid, cur, t['amount'])
            t['base_amount'] = cur_obj.round(cr, uid, cur, t['base_amount'])
            t['tax_amount'] = cur_obj.round(cr, uid, cur, t['tax_amount'])
        return tax_grouped

    _name = "account.invoice.tax"
    _inherit = "account.invoice.tax"


