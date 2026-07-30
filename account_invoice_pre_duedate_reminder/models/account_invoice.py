# Copyright 2020 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    pre_duedate_reminder_mail_id = fields.Many2one(
        comodel_name="mail.mail", string="Pre due date reminder email", copy=False
    )

    @api.model
    def _pre_duedate_reminder_scheduler(self):
        companies = self.env["res.company"].search(
            [("pre_duedate_reminder_interval_days", ">", 0)]
        )
        for company in companies:
            days = company.pre_duedate_reminder_interval_days
            reminder_date = fields.Date.to_string(
                fields.Date.from_string(fields.Date.today()) + timedelta(days=days)
            )
            invoices = self.search(
                [
                    ("state", "=", "posted"),
                    ("pre_duedate_reminder_mail_id", "=", False),
                    ("invoice_date_due", ">=", fields.Date.today()),
                    ("invoice_date_due", "<", reminder_date),
                    ("move_type", "=", "out_invoice"),
                    ("company_id", "=", company.id),
                    ("payment_state", "not in", ("paid", "reversed", "in_payment")),
                    ("commercial_partner_id.no_pre_duedate_reminder", "!=", True),
                ],
            )
            partners_invoices = defaultdict(list)
            for invoice in invoices:
                partners_invoices[invoice.partner_id].append(invoice.id)
            for partner, invoice_ids in partners_invoices.items():
                reminder_partner_id = self._reminder_partner(partner)
                wizard = self.env["pre.duedate.reminder"].create(
                    {
                        "partner_id": reminder_partner_id,
                        "invoice_ids": [(6, 0, invoice_ids)],
                        "company_id": company.id,
                    }
                )
                wizard.generate_mail()

    def _reminder_partner(self, partner):
        partner_id = partner.commercial_partner_id.address_get(["dunning"])["dunning"]
        return partner_id
