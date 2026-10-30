# Copyright 2026 Akretion France (http://www.akretion.com/)
# @author Benoît Guillot <benoit.guillot@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models

MOD = "account_invoice_overdue_reminder_scheduler"


class OverdueReminderStep(models.TransientModel):
    _inherit = "overdue.reminder.step"

    error = fields.Text(
        readonly=True,
        help="Reason why the automatic reminder could not be sent. It is set "
        "by the overdue reminder scheduler and used in the alert e-mail.",
    )

    def _get_overdue_invoice_reminder_alert_template(self):
        return MOD + ".overdue_reminder_alert_mail_template"

    def send_alert_mail(self):
        """Send the alert e-mail for a reminder that could not be sent.

        The recipients are configured on the alert mail template, so that
        they can be changed without code.
        """
        self.ensure_one()
        mail_template = self.env.ref(
            self._get_overdue_invoice_reminder_alert_template()
        )
        mvals = mail_template._generate_template(
            [self.id],
            [
                "subject",
                "body_html",
                "email_from",
                "email_to",
                "partner_to",
                "email_cc",
                "reply_to",
            ],
        )[self.id]
        mvals.update(
            {
                "model": "res.partner",
                "res_id": self.commercial_partner_id.id,
            }
        )
        mvals.pop("attachment_ids", None)
        mvals.pop("attachments", None)
        self.env["mail.mail"].sudo().create(mvals)
