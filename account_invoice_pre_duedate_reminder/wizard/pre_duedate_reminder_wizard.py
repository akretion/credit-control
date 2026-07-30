# Copyright 2020 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64

from odoo import Command, fields, models


class PreDuedateReminder(models.TransientModel):
    _name = "pre.duedate.reminder"
    _description = "Wizard to reminder pre due date customer invoice"

    partner_id = fields.Many2one(
        "res.partner",
        string="Customers",
    )
    invoice_ids = fields.Many2many(comodel_name="account.move", string="Invoices")
    company_id = fields.Many2one(
        "res.company",
        readonly=True,
        required=True,
        default=lambda self: self.env["res.company"]._company_default_get(),
    )

    def generate_mail(self):
        self.ensure_one()
        iao = self.env["ir.attachment"]
        iaro = self.env["ir.actions.report"]
        res_mail_tmpl = self.env.ref(
            "account_invoice_pre_duedate_reminder.pre_duedate_invoice_reminder_mail_template"
        )._generate_template(
            [self.id],
            [
                "subject",
                "body_html",
                "email_from",
                "email_to",
                "partner_to",
                "email_cc",
                "reply_to",
                "scheduled_date",
            ],
        )
        mvals = res_mail_tmpl[self.id]
        mvals.update(
            {
                "model": "res.partner",
                "res_id": self.partner_id.id,
            }
        )
        mvals.pop("attachment_ids", None)
        mvals.pop("attachments", None)
        mail = self.env["mail.mail"].sudo().create(mvals)
        attachment_ids = []
        for inv in self.invoice_ids:
            report_bin, report_format = iaro._render(
                "account.report_invoice_with_payments", [inv.id]
            )
            filename = f"{inv._get_report_base_filename()}.{report_format}"
            attach = iao.create(
                {
                    "name": filename,
                    "datas": base64.b64encode(report_bin),
                    "res_model": "mail.message",
                    "res_id": mail.mail_message_id.id,
                }
            )
            attachment_ids.append(attach.id)
        mail.write({"attachment_ids": [Command.set(attachment_ids)]})
        self.invoice_ids.write({"pre_duedate_reminder_mail_id": mail.id})
