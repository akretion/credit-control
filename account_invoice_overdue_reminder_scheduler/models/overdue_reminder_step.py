# Copyright 2026 Akretion France (http://www.akretion.com/)
# @author Benoît Guillot <benoit.guillot@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, fields, models

MOD = "account_invoice_overdue_reminder_scheduler"


class OverdueReminderStep(models.TransientModel):
    _inherit = "overdue.reminder.step"

    error = fields.Text(
        readonly=True,
        help="Reason why the automatic reminder could not be sent. It is set "
        "by the overdue reminder scheduler and used in the alert e-mail.",
    )

    def _get_unreconciled_credit_note_moves(self):
        """Credit notes of the customer that are not reconciled at all.

        The unreconciled payments and refunds of the customer are computed by the
        reminder wizard and stored on the step: only the refunds (credit notes)
        are kept here.
        """
        self.ensure_one()
        return self.warn_unreconciled_move_line_ids.filtered(
            lambda line: line.move_id.move_type == "out_refund"
        ).move_id

    def _has_unreconciled_credit_note(self):
        self.ensure_one()
        return bool(self._get_unreconciled_credit_note_moves())

    def _get_credit_note_email_to(self):
        """Recipients configured in the Cc field of the reminder mail template."""
        self.ensure_one()
        mail_template = self.env.ref(self._get_overdue_invoice_reminder_template())
        return mail_template._generate_template([self.id], ["email_cc"])[self.id].get(
            "email_cc"
        )

    def generate_mail_vals(self):
        """Send the reminder to the accounting team when the customer has
        unreconciled credit notes.

        The reminder e-mail is unchanged (same subject, body and attachments),
        only its recipients are replaced by the addresses set in the Cc field of
        the reminder mail template: the accounting team receives the reminder
        instead of the customer and can adapt it case by case before sending it.
        """
        vals = super().generate_mail_vals()
        credit_note_email_to = self._get_credit_note_email_to()
        if credit_note_email_to and self._has_unreconciled_credit_note():
            self.env["mail.mail"].sudo().browse(vals["mail_id"]).write(
                {
                    "email_to": credit_note_email_to,
                    "partner_ids": [Command.clear()],
                }
            )
        return vals

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
