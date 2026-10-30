# Copyright 2026 Akretion France (http://www.akretion.com/)
# @author: Benoît Guillot <benoit.guillot@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.account_invoice_overdue_reminder_scheduler.hooks import (
    post_init_hook,
)

MOD = "account_invoice_overdue_reminder_scheduler"


@tagged("post_install", "-at_install")
class TestOverdueReminderScheduler(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write(
            {
                "overdue_reminder_auto_send": True,
                "overdue_reminder_start_days": 0,
                "overdue_reminder_min_interval_days": 5,
                # rendering the invoice PDF requires an external wkhtmltopdf
                # server, which is not part of these tests
                "overdue_reminder_attach_invoice": False,
            }
        )
        # the recipients of the alert e-mails are configured on the mail
        # template
        cls.alert_template = cls.env.ref(MOD + ".overdue_reminder_alert_mail_template")
        cls.alert_template.email_to = "overdue.alert@example.com"
        cls.reminder_template = cls.env.ref(
            "account_invoice_overdue_reminder.overdue_invoice_reminder_mail_template"
        )
        cls.accounting_email = "overdue.accounting@example.com"
        cls.salesman = new_test_user(
            cls.env,
            login="overdue-salesman",
            name="Overdue Salesman",
            email="overdue.salesman@example.com",
            groups="account.group_account_invoice",
        )
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "Overdue Customer",
                "email": "overdue.customer@example.com",
                "user_id": cls.salesman.id,
            }
        )

    def _create_overdue_invoice(self, partner=None, price_unit=100.0):
        # an invoice due 30 days ago, i.e. more than the trigger delay (0 day)
        today = fields.Date.context_today(self.env["account.move"])
        return self._create_invoice_one_line(
            move_type="out_invoice",
            price_unit=price_unit,
            product_id=self.product_a.id,
            partner_id=partner or self.customer,
            invoice_date=today - timedelta(days=60),
            invoice_date_due=today - timedelta(days=30),
            post=True,
        )

    def _create_unreconciled_credit_note(self, price_unit=50.0):
        today = fields.Date.context_today(self.env["account.move"])
        return self._create_invoice_one_line(
            move_type="out_refund",
            price_unit=price_unit,
            product_id=self.product_a.id,
            partner_id=self.customer,
            invoice_date=today - timedelta(days=60),
            invoice_date_due=today - timedelta(days=30),
            post=True,
        )

    def _run_scheduler(self):
        self.env["account.move"]._overdue_reminder_scheduler()

    def _reminder_actions(self, partner):
        return self.env["overdue.reminder.action"].search(
            [("commercial_partner_id", "=", partner.commercial_partner_id.id)]
        )

    def _alert_mails(self):
        return self.env["mail.mail"].search(
            [("email_to", "=", "overdue.alert@example.com")]
        )

    def _create_customer_without_email(self):
        customer = self.env["res.partner"].create({"name": "No Email Customer"})
        # the customer without e-mail is processed first (higher residual)
        self._create_overdue_invoice(partner=customer, price_unit=5000.0)
        return customer

    def test_cron_sends_overdue_reminder(self):
        invoice = self._create_overdue_invoice()
        self.assertFalse(invoice.overdue_reminder_ids)

        self._run_scheduler()

        actions = self._reminder_actions(self.customer)
        self.assertEqual(len(actions), 1)
        action = actions
        self.assertEqual(action.reminder_type, "mail")
        self.assertEqual(action.date, fields.Date.context_today(action))
        # the reminder is sent by the salesman of the customer
        self.assertEqual(action.user_id, self.salesman)
        # the e-mail is queued: it is sent by the 'Mail: Email Queue Manager' cron
        self.assertTrue(action.mail_id)
        self.assertEqual(action.mail_id.state, "outgoing")
        self.assertIn(self.customer.email, action.mail_id.email_to)
        self.assertEqual(action.reminder_count, 1)
        # the reminder is logged on the invoice
        self.assertEqual(action.reminder_ids.invoice_id, invoice)
        self.assertEqual(action.reminder_ids.counter, 1)
        self.assertEqual(invoice.overdue_reminder_counter, 1)
        self.assertEqual(invoice.overdue_reminder_last_date, action.date)
        chatter = " ".join(invoice.message_ids.mapped(lambda m: m.body or ""))
        self.assertIn("Overdue reminder", chatter)
        # everything worked: no alert
        self.assertFalse(self._alert_mails())

    def test_cron_sends_reminder_to_accounting_with_credit_note(self):
        """A customer with an unreconciled credit note is not reminded directly:
        the reminder goes to the accounting team, whose addresses are configured
        on the reminder mail template."""
        self.reminder_template.email_cc = self.accounting_email
        invoice = self._create_overdue_invoice()
        self._create_unreconciled_credit_note()

        self._run_scheduler()

        actions = self._reminder_actions(self.customer)
        self.assertEqual(len(actions), 1)
        action = actions
        self.assertEqual(action.reminder_type, "mail")
        # the reminder e-mail is the usual one, but sent to the accounting team
        self.assertEqual(action.mail_id.email_to, self.accounting_email)
        self.assertFalse(action.mail_id.partner_ids)
        self.assertIn(self.company.name, action.mail_id.subject)
        # the reminder is still logged and counted on the invoice
        self.assertIn(invoice, action.reminder_ids.invoice_id)
        self.assertEqual(invoice.overdue_reminder_counter, 1)
        self.assertFalse(self._alert_mails())

    def test_cron_sends_reminder_to_customer_with_reconciled_credit_note(self):
        """The accounting recipients only apply to unreconciled credit notes."""
        self.reminder_template.email_cc = self.accounting_email
        invoice = self._create_overdue_invoice(price_unit=200.0)
        credit_note = self._create_unreconciled_credit_note()
        (invoice + credit_note).line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        ).reconcile()

        self._run_scheduler()

        actions = self._reminder_actions(self.customer)
        self.assertEqual(len(actions), 1)
        self.assertIn(self.customer.email, actions.mail_id.email_to)
        self.assertNotIn(self.accounting_email, actions.mail_id.email_to)

    def test_cron_sends_reminder_to_customer_without_credit_note(self):
        """Without credit note, the reminder is sent to the customer even if the
        accounting addresses are configured on the mail template."""
        self.reminder_template.email_cc = self.accounting_email
        self._create_overdue_invoice()

        self._run_scheduler()

        actions = self._reminder_actions(self.customer)
        self.assertEqual(len(actions), 1)
        self.assertIn(self.customer.email, actions.mail_id.email_to)
        self.assertNotIn(self.accounting_email, actions.mail_id.email_to)

    def test_reminder_body_lists_the_unreconciled_credit_notes(self):
        """A table of the unreconciled credit notes is added to the reminder
        e-mail, below the table of the overdue invoices."""
        self._create_overdue_invoice()
        credit_note = self._create_unreconciled_credit_note(price_unit=50.0)

        self._run_scheduler()

        action = self._reminder_actions(self.customer)
        body = action.mail_id.body_html
        # the invoices table and the credit notes table
        self.assertEqual(body.count("<table"), 2)
        # the credit note is listed in the invoices table and in the credit notes
        # table (language independent assertions)
        self.assertEqual(body.count(credit_note.name), 2)
        # the body is also available on the reminder step
        step = self.env["overdue.reminder.step"].search(
            [("commercial_partner_id", "=", self.customer.id)]
        )
        self.assertEqual(step.mail_body.count(credit_note.name), 2)

    def test_reminder_body_without_credit_note(self):
        """No credit notes table when the customer has no unreconciled refund."""
        self._create_overdue_invoice()

        self._run_scheduler()

        action = self._reminder_actions(self.customer)
        # only the invoices table
        self.assertEqual(action.mail_id.body_html.count("<table"), 1)

    def test_reminder_template_has_the_credit_notes_table(self):
        """The source body of the reminder template lists the credit notes once,
        and the hook does not modify it."""
        body = self.reminder_template.body_html
        self.assertEqual(body.count("_get_unreconciled_credit_note_moves"), 1)

        post_init_hook(self.env)

        self.assertEqual(self.reminder_template.body_html, body)

    def test_cron_respects_minimum_interval(self):
        invoice = self._create_overdue_invoice()

        self._run_scheduler()
        self.assertEqual(len(self._reminder_actions(self.customer)), 1)

        # the second run must not send a second reminder (min interval) and
        # must not raise, even if there is nothing left to remind
        self._run_scheduler()
        actions = self._reminder_actions(self.customer)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions.reminder_ids.invoice_id, invoice)
        # "nothing to remind" is not a failure: no alert
        self.assertFalse(self._alert_mails())

    def test_cron_alerts_customer_without_email(self):
        no_email_customer = self._create_customer_without_email()
        invoice = self._create_overdue_invoice(self.customer, price_unit=100.0)

        self._run_scheduler()

        # the customer without e-mail is not reminded, the other one is
        self.assertFalse(self._reminder_actions(no_email_customer))
        actions = self._reminder_actions(self.customer)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions.reminder_ids.invoice_id, invoice)

        # an alert e-mail is sent for the customer that could not be reminded
        mails = self._alert_mails()
        self.assertEqual(len(mails), 1)
        mail = mails
        self.assertEqual(mail.state, "outgoing")
        self.assertEqual(mail.model, "res.partner")
        self.assertEqual(mail.res_id, no_email_customer.commercial_partner_id.id)
        self.assertIn("Overdue reminder not sent for", mail.subject)
        self.assertIn(no_email_customer.name, mail.subject)
        self.assertIn("E-mail missing on partner", mail.body_html)
        # the reason is also available on the reminder step
        step = self.env["overdue.reminder.step"].search(
            [("commercial_partner_id", "=", no_email_customer.id)]
        )
        self.assertEqual(len(step), 1)
        self.assertIn("E-mail missing on partner", step.error)

    def test_cron_alert_without_recipient(self):
        """The recipients are the template's responsibility: no crash here."""
        self.alert_template.email_to = False
        no_email_customer = self._create_customer_without_email()

        self._run_scheduler()

        # the alert mail is still created: the mail queue reports the missing
        # recipient and the user fixes the template
        mails = self.env["mail.mail"].search(
            [
                ("model", "=", "res.partner"),
                ("res_id", "=", no_email_customer.commercial_partner_id.id),
            ]
        )
        self.assertEqual(len(mails), 1)
        self.assertFalse(mails.email_to)
        # the failure is available on the reminder step
        step = self.env["overdue.reminder.step"].search(
            [("commercial_partner_id", "=", no_email_customer.id)]
        )
        self.assertEqual(len(step), 1)
        self.assertIn("E-mail missing on partner", step.error)

    def test_cron_wizard_failure_is_raised(self):
        """A failure of the wizard itself is not hidden: it fails the cron."""
        self._create_overdue_invoice()

        with (
            patch.object(
                type(self.env["overdue.reminder.start"]),
                "run",
                side_effect=UserError("Bad configuration"),
            ),
            self.assertRaises(UserError),
        ):
            self._run_scheduler()

        # no reminder was sent and there is nobody to send an alert to
        self.assertFalse(self._reminder_actions(self.customer))
        self.assertFalse(self._alert_mails())

    def test_cron_inactive_on_company(self):
        invoice = self._create_overdue_invoice()
        self.company.overdue_reminder_auto_send = False

        self._run_scheduler()

        self.assertFalse(self._reminder_actions(self.customer))
        self.assertFalse(invoice.overdue_reminder_ids)
        self.assertFalse(self._alert_mails())

    def test_cron_without_overdue_invoice(self):
        # no overdue invoice: the scheduler must not raise and not alert
        self._run_scheduler()
        self.assertFalse(self._reminder_actions(self.customer))
        self.assertFalse(self._alert_mails())
