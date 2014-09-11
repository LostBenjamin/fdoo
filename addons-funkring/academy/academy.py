# -*- coding: utf-8 -*-
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

from openerp.osv import fields, osv
from openerp.addons.at_base import util
from openerp.addons.at_base import extfields
from openerp.addons.at_base import helper
from openerp.tools.translate import _
from openerp import tools

import re

PATTERN_NO = re.compile("^[0-9]+$")

class academy_year(osv.Model):
    _name = "academy.year"
    _columns = {
        "company_id" : fields.many2one("res.company","Company"),
        "name" : fields.char("Name", required=True, select=True),
        "semester_ids" : fields.one2many("academy.semester","year_id","Semester"),
        "date_start" : fields.date("Start", select=True),
        "date_end" : fields.date("End", select=True)
    }
    _defaults = {
        "company_id" : lambda self, cr, uid, context: self.pool.get("res.company")._company_default_get(cr, uid, "academy.year", context=context)
    }
    _order = "name desc"


class academy_semester(osv.Model):

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        reads = self.read(cr, uid, ids, ["name", "year_id"], context=context)
        res = []
        for record in reads:
            name = record["name"]
            if record["year_id"]:
                year_obj = self.pool["academy.year"]
                name = year_obj.browse(cr, uid, record["year_id"][0]).name + " " + name
            res.append((record["id"], name))
        return res

    _name = "academy.semester"
    _columns = {
        "year_id" : fields.many2one("academy.year", "Year", ondelete="cascade", select=True),
        "name" : fields.char("Name", required=True),
        "date_start" : fields.date("Start", required=True),
        "date_end" : fields.date("End", required=True)
    }
    _order ="date_start desc"

class academy_student(osv.Model):

    def onchange_address(self, cr, uid, ids, use_parent_address, parent_id, context=None):
        return self.pool.get("res.partner").onchange_address(cr, uid, ids, use_parent_address, parent_id, context=context)

    def onchange_state(self, cr, uid, ids, state_id, context=None):
        return self.pool.get("res.partner").onchange_state(cr, uid, ids, state_id, context=context)

    def on_change_zip(self, cr, uid, ids, zip_code, city):
        return self.pool.get("res.partner").on_change_zip(cr, uid, ids, zip_code, city)

    def unlink(self, cr, uid, ids, context=None):
        """ Also delete Partner """
        partner_ids = []
        for obj in self.browse(cr, uid, ids, context):
            if obj.partner_id:
                partner_ids.append(obj.partner_id.id)
        res = super(academy_student,self).unlink(cr, uid, ids, context)
        self.pool["res.partner"].unlink(cr, uid, partner_ids, context)
        return res

    def _default_country_id(self, cr, uid, context=None):
        company_obj = self.pool['res.company']
        company_id = company_obj._company_default_get(cr, uid, 'res.partner', context=context)
        if company_id:
            company = company_obj.browse(cr, uid, company_id, context=context)
            country = company.country_id
            return country and country.id or None
        return None

    _name = "academy.student"
    _inherits = {"res.partner":"partner_id"}
    _columns = {
        "partner_id" : fields.many2one("res.partner", "Partner", ondelete="restrict", required=True, select=True),
        "registration_ids" : fields.one2many("academy.registration","student_id","Registrations"),
        "tmp_partner_id" : extfields.duplicate("partner_id", "Partner", type="many2one", obj="res.partner"),
        "nationality" : fields.char("Nationality")
    }
    _defaults = {
        "customer" : True,
        "country_id": _default_country_id
    }


class academy_location(osv.Model):

    def onchange_address(self, cr, uid, ids, use_parent_address, parent_id, context=None):
        return self.pool.get("res.partner").onchange_address(cr, uid, ids, use_parent_address, parent_id, context=context)

    def onchange_state(self, cr, uid, ids, state_id, context=None):
        return self.pool.get("res.partner").onchange_state(cr, uid, ids, state_id, context=context)

    def on_change_zip(self, cr, uid, ids, zip_code, city):
        return self.pool.get("res.partner").on_change_zip(cr, uid, ids, zip_code, city)
    
    _name = "academy.location"
    _inherits = { "res.partner" : "address_id" }
    _columns = {
        "address_id" : fields.many2one("res.partner", "Address", ondelete="restrict",  required=True, select=True)
    }

class academy_course_product(osv.Model):

    def onchange_uom(self, cr, uid, ids, uom_id, uom_po_id):
        return self.pool.get("product.product").onchange_uom(cr, uid, ids, uom_id, uom_po_id)

    def _uom_categ_id(self, cr, uid, ids, field_name, arg, context=None):
        res = dict.fromkeys(ids)
        for obj in self.browse(cr, uid, ids, context):
            res[obj.id]=obj.uom_id.category_id.id
        return res

    def unlink(self, cr, uid, ids, context=None):
        """ Also delete Product """
        product_ids = []
        for obj in self.browse(cr, uid, ids, context):
            if obj.product_id:
                product_ids.append(obj.product_id.id)
        res = super(academy_course_product,self).unlink(cr, uid, ids, context)
        self.pool["product.product"].unlink(cr, uid, product_ids, context)
        return res

    _name = "academy.course.product"
    _inherits = {"product.product":"product_id"}
    _columns = {
        "product_id" : fields.many2one("product.product", "Product", ondelete="restrict", required=True, select=True),
        "course_uom_ids" : fields.many2many("product.uom", "course_uom_rel", "course_id", "uom_id", "Units"),
        "uom_categ_id" : fields.function(_uom_categ_id, type="many2one", obj="product.uom.categ", string="Unit Category"),
        "sequence" : fields.integer("Sequence")
    }
    _defaults= {
        "sale_ok" : True,
        "type" : "service",
        "sequence" : 10
    }
    _order = "sequence"


class academy_registration(osv.Model):

    def _send_mails(self, cr, uid, template_xmlid, ids, context=None):
        template_obj = self.pool["email.template"]
        template_id = self.pool["ir.model.data"].xmlid_to_res_id(cr, uid, template_xmlid)
        if template_id:
            for reg in self.browse(cr, uid, ids, context=context):
                mail_context = context and dict(context) or {}

                partner_ids = [str(reg.student_id.partner_id.id)]
                if reg.student_id.parent_id:
                    partner_ids.append(str(reg.student_id.parent_id.id))
                if reg.invoice_address_id:
                    partner_ids.append(str(reg.invoice_address_id.id))

                mail_context["partner_to"]=",".join(partner_ids)
                template_obj.send_mail(cr, uid, template_id, reg.id, force_send=True, context=mail_context)

    def _next_sequence(self, cr, uid, context=None):
        return self.pool.get("ir.sequence").get(cr, uid, "academy.registration")

    def _get_semester_id(self, cr, uid, context=None):
        
        # get current semester        
        user = self.pool["res.users"].browse(cr, uid, uid, context)
        semester = user.company_id.academy_semester_id
        if semester:
            return semester.id
        
        # search semester based on date if current semester is not set
        semester_obj = self.pool["academy.semester"]
        #search next semester
        semester_ids = semester_obj.search(cr, uid, [("date_start", ">", util.currentDate())], order="date_start asc")
        if not semester_ids:
            # get current semester
            return semester_obj.search_id(cr, uid, [], order="date_end desc")
        return semester_ids and semester_ids[0] or None

    def _calc_hours(self, cr, uid, uom, amount, context=None):
        if uom and amount:
            uom_obj = self.pool["product.uom"]
            if uom.factor == 1.0:
                return amount
            else:
                base_uom_id=uom_obj.search_id(cr, uid, [("category_id","=",uom.category_id.id),("factor","=",1.0)])
                return uom_obj._compute_qty(cr, uid, uom.id, amount, base_uom_id, round=False)
        return 0.0

    def _hours(self, cr, uid, ids, field_name, arg, context=None):
        res = dict.fromkeys(ids,0.0)
        for obj in self.browse(cr, uid, ids, context):
            res[obj.id]=self._calc_hours(cr, uid, obj.uom_id, obj.amount, context)
        return res

    def message_get_default_recipients(self, cr, uid, ids, context=None):
        res = super(academy_registration,self).message_get_default_recipients(cr, uid, ids, context=context)
        for reg in self.browse(cr, uid, ids, context=context):
            partner_ids = res[reg.id]["partner_ids"]
            for p in reg.student_id.partner_ids:
                if not p.id in partner_ids:
                    partner_ids.append(p.id)
        return res

    def do_register(self, cr, uid, ids, check=False, context=None):
        ids = self.search(cr, uid, [("id","in",ids),("state","=","draft")])
        if check:
            self.write(cr, uid, ids, {"state" : "check"}, context=context)
        else:
            self.write(cr, uid, ids, {"state" : "registered"}, context=context)
        self._send_mails(cr, uid, "academy.email_template_registration", ids, context=context)
        return True

    def do_check(self, cr, uid, ids, context=None):
        ids = self.search(cr, uid, [("id","in",ids),("state","=","check")])
        self.write(cr, uid, ids, {"state" : "registered"}, context=context)
        return True

    def do_cancel(self, cr, uid, ids, context=None):
        ids = self.search(cr, uid, [("id","in",ids),("state","in",["registered","assigned","open"])])
        self.write(cr, uid, ids, {"state" : "cancel"}, context=context)
        self._send_mails(cr, uid, "academy.email_template_registration_cancel", ids, context=context)
        return True

    def do_draft(self, cr, uid, ids, context=None):
        ids = self.search(cr, uid, [("id","in",ids),("state","=","cancel")])
        self.write(cr, uid, ids, {"state" : "draft"}, context=context)
        return True

    def create(self, cr, uid, vals, context=None):
        name = vals.get("name")
        if not name or name == "/":
            vals["name"]=self._next_sequence(cr, uid, context)
        return super(academy_registration,self).create(cr, uid, vals, context=context)

    def onchange_course_prod(self, cr, uid, ids, course_prod_id, uom_id, context=None):
        val = {}
        res = { "value" : val}
        if course_prod_id:
            course_prod = self.pool["academy.course.product"].browse(cr, uid, course_prod_id, context=context)
            if course_prod:
                uom_ids = [uom.id for uom in course_prod.course_uom_ids]
                val["course_uom_ids"] = uom_ids
                if uom_id and not uom_id in uom_ids:
                    val["uom_id"]=None
        return res

    def onchange_uom(self, cr, uid, ids, uom_id, amount, context=None):
        hours = 0.0
        if uom_id and amount:
            uom = self.pool["product.uom"].browse(cr, uid, uom_id, context=context)
            hours = self._calc_hours(cr, uid, uom, amount, context)
        return {"value" : {"hours":hours} }

    def onchange_unreg_semester(self, cr, uid, ids, semester_id, unreg_semester_id, context=None):
        res = {"value": {}}

        if semester_id and unreg_semester_id:
            semester_obj = self.pool["academy.semester"]
            semester_date_start = semester_obj.browse(cr, uid, semester_id, context=context).date_start
            unreg_semester_date_start = semester_obj.browse(cr, uid, unreg_semester_id, context=context).date_start
            if  semester_date_start > unreg_semester_date_start:
                res["value"]["unreg_semester_id"] = None

        return res

    def _use_invoice_address_id(self, cr, uid, ids, field_name, args, context=None):
        res = dict.fromkeys(ids)
        for obj in self.browse(cr, uid, ids):
            if obj.invoice_address_id:
                res[obj.id] = obj.invoice_address_id.id
            elif obj.student_id.parent_id:
                res[obj.id] = obj.student_id.parent_id.id
            else:
                res[obj.id] = obj.student_id.partner_id.id
        return res

    def unlink(self, cr, uid, ids, context=None):
        for reg in self.browse(cr, uid, ids, context):
            if not reg.state in ("draft", "cancel", "check"):
                raise osv.except_osv(_("Error!"), _("Can not delete registrations, which are not in state 'Draft' or 'Cancelled'"))
        return super(academy_registration, self).unlink(cr, uid, ids, context)


    _inherit = ["mail.thread"]
    _name = "academy.registration"
    _description = "Academy Registration"
    _columns = {
        "name" : fields.char("Number", readonly=True, select=True),
        "create_date" : fields.datetime("Create Date", select=True, readonly=True),
        "user_id" : fields.many2one("res.users","Agent", select=True),
        "semester_id" : fields.many2one("academy.semester", "Registration", select=True, required=True, ondelete="restrict"),
        "unreg_semester_id" : fields.many2one("academy.semester", "Deregistration", ondelete="restrict",
                                              help="The start date from the ending semester must be smaller or equal than the start datum from the beginning semester"),
        "intership_date" : fields.date("Intership Date", help="This Date must be set, if there was an intership during the semester."),
        "student_id" : fields.many2one("academy.student", "Student", select=True, required=True, ondelete="restrict"),
        "student_parent_id" : fields.related("student_id", "parent_id", type="many2one", relation="res.partner", string="Parent", store=True, readonly=True),
        "location_id" : fields.many2one("academy.location", "Location", select=True, ondelete="restrict"),
        "student_of_loc" : fields.boolean("Is student of location?"),
        "course_prod_id" : fields.many2one("academy.course.product", "Product", select=True, required=True, ondelete="restrict"),
        "course_id" : fields.many2one("academy.course", "Course", select=True, ondelete="restrict"),
        "trainer_id" : fields.many2one("academy.trainer", "Trainer", select=True, ondelete="restrict"),
        "amount" : fields.float("Amount", required=True),
        "hours" : fields.function(_hours, type="float", store=True, readonly=True, string="Hours"),
        "uom_id" : fields.many2one("product.uom", "Unit", select=True, ondelete="restrict"),
        "invoice_address_id" : fields.many2one("res.partner","Invoice Address"),
        "use_invoice_address_id" : fields.function(_use_invoice_address_id, type="many2one", obj="res.partner", string="Determined invoice address"),
        "course_uom_ids" : fields.related("course_prod_id", "course_uom_ids", type="many2many", relation="product.uom", string="Course Units"),
        "state" : fields.selection([("draft","Draft"),
                                    ("cancel","Cancel"),
                                    ("check","Check"),
                                    ("registered","Registered"),
                                    ("assigned","Assigned")],
                                    "State", readonly=True, select=True),
        "note" : fields.text("Note", select=True),

    }
    _sql_constraints = [
        ("name_uniq", "unique(name)", "Registration name must be unique"),
    ]
    _defaults = {
        "amount" : 1.0,
        "state" : "draft",
        "name" : "/",
        "user_id" : lambda self, cr, uid, context: uid,
        "semester_id" : _get_semester_id
    }
    _order = "create_date desc"


class academy_trainer(osv.Model):

    def onchange_address(self, cr, uid, ids, use_parent_address, parent_id, context=None):
        return self.pool.get("res.partner").onchange_address(cr, uid, ids, use_parent_address, parent_id, context=context)

    def onchange_state(self, cr, uid, ids, state_id, context=None):
        return self.pool.get("res.partner").onchange_state(cr, uid, ids, state_id, context=None)

    def on_change_zip(self, cr, uid, ids, zip_code, city):
        return self.pool.get("res.partner").on_change_zip(cr, uid, ids, zip_code, city)

    _name = "academy.trainer"
    _description = "Academy Trainer"
    _inherits = {"res.partner":"partner_id"}
    _columns = {
        "partner_id" : fields.many2one("res.partner", "Partner", required=True, ondelete="restrict"),
        "contract_ids" : fields.one2many("academy.contract", "trainer_id", "Contracts")
    }


class academy_course(osv.Model):
    _name = "academy.course"
    _description = "Academy Course"
    _columns = {
        "name" : fields.char("Name", size=64, required=True),
        "description" : fields.text("Description"),
        "number" : fields.char("Number"),
        "date_from" : fields.datetime("Date from"),
        "date_to" : fields.datetime("Date to"),
        "topic_ids" : fields.one2many("academy.topic", "course_id", "Topics"),
        "trainer_ids" : fields.many2many("academy.trainer", "academy_trainer_course_rel", "trainer_id", "course_id", "Trainers"),
        "student_ids" : fields.many2many("res.partner", "partner_academy_course_rel", "course_id", "student_id", "Students"),

    }

class academy_topic(osv.Model):
    _name = "academy.topic"
    _description = "Academy Topic"
    _columns = {
        "name" : fields.char("Name", size=64, required=True),
        "course_id" : fields.many2one("academy.course", "Course", required=True),
        "description" : fields.text("Description"),
        "duration" : fields.float("Unit(s)"),
        "contract_ids" : fields.many2many("academy.contract", "academy_topic_contract_rel", "contract_id", "topic_id", "Contracts"),
    }


class academy_contract(osv.Model):
    _name = "academy.contract"
    _description = "Academy Contract"
    _columns = {
        "name" : fields.char("Name", size=64, required=True),
        "date_start" : fields.datetime("Date start"),
        "date_end" : fields.datetime("Date end"),
        "topic_ids" : fields.many2many("academy.topic", "academy_topic_contract_rel", "topic_id", "contract_id", "Courses"),
        "trainer_id" : fields.many2one("academy.trainer", "Trainer", ondelete="restrict")
    }


class academy_journal(osv.Model):
    _name = "academy.journal"
    _description = "Academy Journal"

    def onchange_topic(self, cr, uid, ids, topic_id, context=None):
        res = {
            "value" : {}
        }

        if topic_id:
            topic = self.pool.get("academy.topic").browse(cr, uid, topic_id)
            res["value"]["name"] = str(topic.name)+"\n"+str(topic.description)
            res["value"]["duration"] = topic.duration
            res["value"]["course_id"] = topic.course_id.id

        return res

    _columns = {
        "name" : fields.text("Name"),
        "date" : fields.date("Date", required=True),
        "begin" : fields.float("Begin", help="The time must be between 00:00 and 24:00 o'clock and must not be bigger than the end"),
        "end" : fields.float("End", help="The time must be between 00:00 and 24:00 o'clock"),
        "topic_id" : fields.many2one("academy.topic", "Topic", required=True),
        "student_ids" : fields.many2many("res.partner", "res_partner_journal_rel", "partner_id", "journal_id", "Students"),
        "absence_ids" : fields.one2many("academy.journal.absence", "journal_id", "Absences"),
        "trainer_id" : fields.many2one("academy.trainer", "Trainer", required=True),
        "course_id" : fields.related("topic_id", "course_id", type="many2one", readonly=True, relation="academy.course", string="Course"),
        "duration" : fields.float("Unit(s)"),
        "expenses" : fields.float("Transport Expenses"),
        "place" : fields.char("Place", size=64)
    }

    _defaults = {
        "date" : util.currentDate(),
    }


class academy_journal_absence(osv.Model):
    _name = "academy.journal.absence"
    _description = "Academy Journal Absence"

    _columns = {
        "name" : fields.char("Reason", size=64, required=True),
        "time_from" : fields.float("From", help="The time must be between 00:00 and 24:00 o'clock and must not be bigger than the end"),
        "time_to" : fields.float("To", help="The time must be between 00:00 and 24:00 o'clock"),
        "partner_id" : fields.many2one("res.partner", "Partner"),
        "journal_id" : fields.many2one("academy.journal", "Journal"),
    }


class academy_registration_invoice(osv.Model):
    _name = "academy.registration.invoice"
    _description = "Academy registration invoice"
    
    _columns = {
        "registration_id" : fields.many2one("academy.registration", "Registration", select=True, ondelete="restrict"),
        "semester_id" : fields.many2one("academy.semester", "Semester", select=True, ondelete="restrict"),
        "invoice_id" : fields.many2one("account.invoice", "Invoice", select=True, ondelete="cascade")
    }


class academy_fee(osv.Model):
    
    def onchange_uom(self, cursor, user, ids, uom_id, uom_po_id):
         return self.pool["product.product"].onchange_uom(cursor, user, ids, uom_id, uom_po_id)
    
    def unlink(self, cr, uid, ids, context=None):
        """ Also delete Product """
        product_ids = []
        for obj in self.browse(cr, uid, ids, context):
            if obj.product_id:
                product_ids.append(obj.product_id.id)
        res = super(academy_fee,self).unlink(cr, uid, ids, context)
        self.pool["product.product"].unlink(cr, uid, product_ids, context)
        return res
    
    _name = "academy.fee"
    _description = "Academy Fee"
    _inherits = { "product.product" : "product_id" }
    
    _columns = {
        "location_category_ids" : fields.many2many("res.partner.category", "academy_fee_id", "category_id", string="Locations"),
        "apply_uom_id" : fields.boolean("Apply on all with same unit"),
        "product_id" : fields.many2one("product.product", "Product", select=True, ondelete="restrict", required=True),
        "sibling_discount" : fields.float("Sibling Discount"),    
        "sequence" : fields.integer("Sequence")
    }
    _defaults = {
        "sequence" : 10   
    }
    _order = "sequence asc"





