# Copyright 2020 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    pre_duedate_reminder_mail_id = fields.Many2one(
        comodel_name="mail.mail", string="Last Pre Due Date Reminder Email", copy=False
    )
    pre_duedate_reminder_count = fields.Integer(
        string="Number of Pre Due Date Reminders",
        copy=False,
        readonly=True,
        help="Number of pre due date reminders already sent for this invoice. "
        "It drives which reminder delay is used: the invoice is reminded at "
        "the delay of rank N when N reminders have already been sent.",
    )

    @api.model
    def _pre_duedate_reminder_scheduler(self):
        companies = self.env["res.company"].search([])
        today = fields.Date.today()
        for company in companies:
            delays = company._get_pre_duedate_reminder_delays()
            if not delays:
                continue
            # an invoice is reminded only once per cron run, even if its due
            # date is already within the window of several delays
            reminded_invoice_ids = []
            for counter, delay in enumerate(delays):
                reminder_date = fields.Date.to_string(today + timedelta(days=delay))
                invoices = self.search(
                    [
                        ("state", "=", "posted"),
                        ("pre_duedate_reminder_count", "=", counter),
                        ("id", "not in", reminded_invoice_ids),
                        ("invoice_date_due", ">=", today),
                        ("invoice_date_due", "<", reminder_date),
                        ("move_type", "=", "out_invoice"),
                        ("company_id", "=", company.id),
                        (
                            "payment_state",
                            "not in",
                            ("paid", "reversed", "in_payment"),
                        ),
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
                    reminded_invoice_ids += invoice_ids

    def _reminder_partner(self, partner):
        partner_id = partner.commercial_partner_id.address_get(["dunning"])["dunning"]
        return partner_id
