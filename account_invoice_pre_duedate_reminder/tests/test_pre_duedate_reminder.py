# Copyright 2026 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import common


class TestPreDuedateReminder(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                mail_create_nolog=True,
                mail_create_nosubscribe=True,
                mail_notrack=True,
                no_reset_password=True,
                tracking_disable=True,
            )
        )

        cls.company = cls.env.company
        # two reminders: 10 days and 5 days before the due date
        cls.company.pre_duedate_reminder_interval_days = "10,5"

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Customer",
                "email": "test-customer@example.com",
            }
        )

        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.account = cls.env["account.account"].search(
            [
                ("company_ids", "in", cls.company.id),
                (
                    "account_type",
                    "=",
                    "income",
                ),
            ],
            limit=1,
        )

    def _create_invoice(
        self, invoice_date_due, state="posted", payment_state="not_paid"
    ):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_due": invoice_date_due,
                "journal_id": self.journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test line",
                            "account_id": self.account.id,
                            "quantity": 1.0,
                            "price_unit": 100.0,
                        },
                    ),
                ],
            }
        )
        if state == "posted":
            invoice.action_post()
        return invoice

    def _due_in(self, days):
        """Due date in N days (0 = today)."""
        return fields.Date.today() + timedelta(days=days)

    def _run_scheduler(self):
        self.env["account.move"]._pre_duedate_reminder_scheduler()

    def test_scheduler_sends_reminder_within_window(self):
        """Invoice due in 3 days should get a reminder (delays = 10,5 days)."""
        invoice = self._create_invoice(self._due_in(3))

        self.assertFalse(invoice.pre_duedate_reminder_mail_id)

        self._run_scheduler()

        invoice.invalidate_recordset()
        self.assertTrue(
            invoice.pre_duedate_reminder_mail_id,
            "A reminder mail should have been created for an invoice due within the "
            "window.",
        )
        self.assertEqual(invoice.pre_duedate_reminder_count, 1)
        # Check that the mail has attachments (the invoice PDF)
        mail = invoice.pre_duedate_reminder_mail_id
        self.assertTrue(
            mail.attachment_ids,
            "The reminder mail should have the invoice PDF attached.",
        )

    def test_scheduler_ignores_invoice_outside_window(self):
        """Invoice due in 11 days should NOT get a reminder (delays = 10,5)."""
        invoice = self._create_invoice(self._due_in(11))

        self._run_scheduler()

        invoice.invalidate_recordset()
        self.assertFalse(
            invoice.pre_duedate_reminder_mail_id,
            "No reminder should be sent for an invoice due outside the window.",
        )
        self.assertEqual(invoice.pre_duedate_reminder_count, 0)

    def test_scheduler_ignores_paid_invoice(self):
        """A paid invoice should NOT get a reminder even if due within the window."""
        invoice = self._create_invoice(self._due_in(3))
        invoice.payment_state = "paid"

        self._run_scheduler()

        invoice.invalidate_recordset()
        self.assertFalse(invoice.pre_duedate_reminder_mail_id)

    def test_scheduler_ignores_draft_invoice(self):
        """A draft invoice should NOT get a reminder."""
        invoice = self._create_invoice(self._due_in(3), state="draft")

        self._run_scheduler()

        invoice.invalidate_recordset()
        self.assertFalse(invoice.pre_duedate_reminder_mail_id)

    def test_scheduler_ignores_overdue_invoice(self):
        """
        An already overdue invoice (due date in the past) should NOT get a reminder.
        """
        invoice = self._create_invoice(self._due_in(-2))

        self._run_scheduler()

        invoice.invalidate_recordset()
        self.assertFalse(invoice.pre_duedate_reminder_mail_id)

    def test_scheduler_ignores_supplier_invoice(self):
        """A supplier invoice (in_invoice) should NOT get a reminder."""
        invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_due": self._due_in(3),
                "journal_id": self.env["account.journal"]
                .search(
                    [
                        ("type", "=", "purchase"),
                        ("company_id", "=", self.company.id),
                    ],
                    limit=1,
                )
                .id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Test line",
                            "account_id": self.env["account.account"]
                            .search(
                                [
                                    ("company_ids", "in", self.company.id),
                                    (
                                        "account_type",
                                        "=",
                                        "expense",
                                    ),
                                ],
                                limit=1,
                            )
                            .id,
                            "quantity": 1.0,
                            "price_unit": 50.0,
                        },
                    ),
                ],
            }
        )
        invoice.action_post()

        self._run_scheduler()

        invoice.invalidate_recordset()
        self.assertFalse(invoice.pre_duedate_reminder_mail_id)

    def test_scheduler_does_not_send_twice_the_same_delay(self):
        """An invoice already reminded for a delay should not be reminded again."""
        self.company.pre_duedate_reminder_interval_days = "5"
        invoice = self._create_invoice(self._due_in(3))

        # First run
        self._run_scheduler()
        invoice.invalidate_recordset()
        first_mail = invoice.pre_duedate_reminder_mail_id
        self.assertTrue(first_mail)
        self.assertEqual(invoice.pre_duedate_reminder_count, 1)

        # Second run
        self._run_scheduler()
        invoice.invalidate_recordset()
        self.assertEqual(
            invoice.pre_duedate_reminder_mail_id,
            first_mail,
            "The same mail should remain; no duplicate should be created.",
        )
        self.assertEqual(invoice.pre_duedate_reminder_count, 1)

    def test_scheduler_reminds_once_per_run(self):
        """Even inside several windows, only one reminder is sent per cron run."""
        invoice = self._create_invoice(self._due_in(3))

        self._run_scheduler()
        invoice.invalidate_recordset()
        self.assertEqual(
            invoice.pre_duedate_reminder_count,
            1,
            "Only one reminder must be sent per cron run.",
        )

        self._run_scheduler()
        invoice.invalidate_recordset()
        self.assertEqual(invoice.pre_duedate_reminder_count, 2)

    def test_scheduler_two_delays(self):
        """Two reminders: one at the 1st delay, one when the 2nd delay is reached."""
        invoice = self._create_invoice(self._due_in(7))

        self._run_scheduler()
        invoice.invalidate_recordset()
        first_mail = invoice.pre_duedate_reminder_mail_id
        self.assertEqual(invoice.pre_duedate_reminder_count, 1)

        # the 2nd delay (5 days) is not reached yet: no new reminder
        self._run_scheduler()
        invoice.invalidate_recordset()
        self.assertEqual(invoice.pre_duedate_reminder_count, 1)

        # 4 days before the due date: the 2nd delay is reached
        invoice.invoice_date_due = self._due_in(4)
        self._run_scheduler()
        invoice.invalidate_recordset()
        self.assertEqual(invoice.pre_duedate_reminder_count, 2)
        self.assertNotEqual(
            invoice.pre_duedate_reminder_mail_id,
            first_mail,
            "The second reminder must be a new e-mail.",
        )

        # and there is no 3rd delay
        self._run_scheduler()
        invoice.invalidate_recordset()
        self.assertEqual(invoice.pre_duedate_reminder_count, 2)

    def test_scheduler_three_delays(self):
        """The number of reminders follows the number of configured delays."""
        self.company.pre_duedate_reminder_interval_days = "15,10,5"
        invoice = self._create_invoice(self._due_in(12))

        # 1st reminder, for the delay of 15 days
        self._run_scheduler()
        invoice.invalidate_recordset()
        self.assertEqual(invoice.pre_duedate_reminder_count, 1)

        # 2nd reminder, for the delay of 10 days
        invoice.invoice_date_due = self._due_in(7)
        self._run_scheduler()
        invoice.invalidate_recordset()
        self.assertEqual(invoice.pre_duedate_reminder_count, 2)

        # 3rd reminder, for the delay of 5 days
        invoice.invoice_date_due = self._due_in(4)
        self._run_scheduler()
        invoice.invalidate_recordset()
        self.assertEqual(invoice.pre_duedate_reminder_count, 3)

        # no 4th delay configured
        self._run_scheduler()
        invoice.invalidate_recordset()
        self.assertEqual(invoice.pre_duedate_reminder_count, 3)

    def test_scheduler_groups_by_partner(self):
        """
        Multiple invoices for the same partner should produce a single wizard/mail.
        """
        inv1 = self._create_invoice(self._due_in(3))
        inv2 = self._create_invoice(self._due_in(3))

        self._run_scheduler()

        inv1.invalidate_recordset()
        inv2.invalidate_recordset()
        self.assertTrue(inv1.pre_duedate_reminder_mail_id)
        self.assertTrue(inv2.pre_duedate_reminder_mail_id)
        # Both invoices should share the same mail
        self.assertEqual(
            inv1.pre_duedate_reminder_mail_id,
            inv2.pre_duedate_reminder_mail_id,
            "Invoices for the same partner should share the same reminder mail.",
        )
        # The mail should have 2 attachments (one PDF per invoice)
        mail = inv1.pre_duedate_reminder_mail_id
        self.assertEqual(
            len(mail.attachment_ids),
            2,
            "The reminder mail should have one PDF attachment per invoice.",
        )

    def test_scheduler_disabled(self):
        """When no delay is configured, no reminder should be sent."""
        self.company.pre_duedate_reminder_interval_days = False
        invoice = self._create_invoice(self._due_in(3))

        self._run_scheduler()

        invoice.invalidate_recordset()
        self.assertFalse(invoice.pre_duedate_reminder_mail_id)

    def test_scheduler_zero_delay_disabled(self):
        """A zero delay must not send any reminder."""
        self.company.pre_duedate_reminder_interval_days = "0"
        invoice = self._create_invoice(self._due_in(3))

        self._run_scheduler()

        invoice.invalidate_recordset()
        self.assertFalse(invoice.pre_duedate_reminder_mail_id)

    def test_get_pre_duedate_reminder_delays(self):
        self.assertEqual(self.company._get_pre_duedate_reminder_delays(), [10, 5])
        self.company.pre_duedate_reminder_interval_days = "5"
        self.assertEqual(self.company._get_pre_duedate_reminder_delays(), [5])
        self.company.pre_duedate_reminder_interval_days = " 10, 5 ,10"
        self.assertEqual(self.company._get_pre_duedate_reminder_delays(), [10, 5])
        self.company.pre_duedate_reminder_interval_days = "0"
        self.assertEqual(self.company._get_pre_duedate_reminder_delays(), [])
        self.company.pre_duedate_reminder_interval_days = False
        self.assertEqual(self.company._get_pre_duedate_reminder_delays(), [])

    def test_invalid_delays(self):
        for value in ("abc", "10;5", "-5", "10,", "5 days"):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.company.pre_duedate_reminder_interval_days = value

    def test_wizard_generate_mail(self):
        """Directly test the wizard to ensure it creates a mail with attachments."""
        invoice = self._create_invoice(self._due_in(3))

        wizard = self.env["pre.duedate.reminder"].create(
            {
                "partner_id": self.partner.id,
                "invoice_ids": [(6, 0, [invoice.id])],
                "company_id": self.company.id,
            }
        )
        wizard.generate_mail()

        invoice.invalidate_recordset()
        self.assertTrue(
            invoice.pre_duedate_reminder_mail_id,
            "The wizard should set pre_duedate_reminder_mail_id on the invoice.",
        )
        self.assertEqual(invoice.pre_duedate_reminder_count, 1)
        mail = invoice.pre_duedate_reminder_mail_id
        self.assertEqual(mail.res_id, self.partner.id)
        self.assertEqual(mail.model, "res.partner")
        self.assertTrue(
            mail.attachment_ids,
            "The wizard should attach the invoice PDF to the mail.",
        )
