# Copyright 2026 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import fields
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
        cls.company.pre_duedate_reminder_interval_days = 5

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

    def test_scheduler_sends_reminder_within_window(self):
        """Invoice due in 3 days should get a reminder (interval = 5 days)."""
        due_date = fields.Date.today() + timedelta(days=3)
        invoice = self._create_invoice(due_date)

        self.assertFalse(invoice.pre_duedate_reminder_mail_id)

        self.env["account.move"]._pre_duedate_reminder_scheduler()

        invoice.invalidate_model()
        self.assertTrue(
            invoice.pre_duedate_reminder_mail_id,
            "A reminder mail should have been created for an invoice due within the "
            "window.",
        )
        # Check that the mail has attachments (the invoice PDF)
        mail = invoice.pre_duedate_reminder_mail_id
        self.assertTrue(
            mail.attachment_ids,
            "The reminder mail should have the invoice PDF attached.",
        )

    def test_scheduler_ignores_invoice_outside_window(self):
        """Invoice due in 10 days should NOT get a reminder (interval = 5 days)."""
        due_date = fields.Date.today() + timedelta(days=10)
        invoice = self._create_invoice(due_date)

        self.env["account.move"]._pre_duedate_reminder_scheduler()

        invoice.invalidate_model()
        self.assertFalse(
            invoice.pre_duedate_reminder_mail_id,
            "No reminder should be sent for an invoice due outside the window.",
        )

    def test_scheduler_ignores_paid_invoice(self):
        """A paid invoice should NOT get a reminder even if due within the window."""
        due_date = fields.Date.today() + timedelta(days=3)
        invoice = self._create_invoice(due_date)
        # Simulate paid state
        invoice.payment_state = "paid"

        self.env["account.move"]._pre_duedate_reminder_scheduler()

        invoice.invalidate_model()
        self.assertFalse(
            invoice.pre_duedate_reminder_mail_id,
            "No reminder should be sent for a paid invoice.",
        )

    def test_scheduler_ignores_draft_invoice(self):
        """A draft invoice should NOT get a reminder."""
        due_date = fields.Date.today() + timedelta(days=3)
        invoice = self._create_invoice(due_date, state="draft")

        self.env["account.move"]._pre_duedate_reminder_scheduler()

        invoice.invalidate_model()
        self.assertFalse(
            invoice.pre_duedate_reminder_mail_id,
            "No reminder should be sent for a draft invoice.",
        )

    def test_scheduler_ignores_overdue_invoice(self):
        """
        An already overdue invoice (due date in the past) should NOT get a reminder.
        """
        due_date = fields.Date.today() - timedelta(days=2)
        invoice = self._create_invoice(due_date)

        self.env["account.move"]._pre_duedate_reminder_scheduler()

        invoice.invalidate_model()
        self.assertFalse(
            invoice.pre_duedate_reminder_mail_id,
            "No reminder should be sent for an overdue invoice.",
        )

    def test_scheduler_ignores_supplier_invoice(self):
        """A supplier invoice (in_invoice) should NOT get a reminder."""
        invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_due": fields.Date.today() + timedelta(days=3),
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

        self.env["account.move"]._pre_duedate_reminder_scheduler()

        invoice.invalidate_model()
        self.assertFalse(
            invoice.pre_duedate_reminder_mail_id,
            "No reminder should be sent for a supplier invoice.",
        )

    def test_scheduler_does_not_send_duplicate(self):
        """An invoice that already got a reminder should NOT get another one."""
        due_date = fields.Date.today() + timedelta(days=3)
        invoice = self._create_invoice(due_date)

        # First run
        self.env["account.move"]._pre_duedate_reminder_scheduler()
        invoice.invalidate_model()
        first_mail = invoice.pre_duedate_reminder_mail_id
        self.assertTrue(first_mail)

        # Second run
        self.env["account.move"]._pre_duedate_reminder_scheduler()
        invoice.invalidate_model()
        self.assertEqual(
            invoice.pre_duedate_reminder_mail_id,
            first_mail,
            "The same mail should remain; no duplicate should be created.",
        )

    def test_scheduler_groups_by_partner(self):
        """
        Multiple invoices for the same partner should produce a single wizard/mail.
        """
        due_date = fields.Date.today() + timedelta(days=3)
        inv1 = self._create_invoice(due_date)
        inv2 = self._create_invoice(due_date)

        self.env["account.move"]._pre_duedate_reminder_scheduler()

        inv1.invalidate_model()
        inv2.invalidate_model()
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

    def test_company_interval_zero_disables_feature(self):
        """
        When pre_duedate_reminder_interval_days is 0, no reminders should be sent.
        """
        self.company.pre_duedate_reminder_interval_days = 0
        due_date = fields.Date.today() + timedelta(days=3)
        invoice = self._create_invoice(due_date)

        self.env["account.move"]._pre_duedate_reminder_scheduler()

        invoice.invalidate_model()
        self.assertFalse(
            invoice.pre_duedate_reminder_mail_id,
            "No reminder should be sent when the interval is 0.",
        )

    def test_wizard_generate_mail(self):
        """Directly test the wizard to ensure it creates a mail with attachments."""
        due_date = fields.Date.today() + timedelta(days=3)
        invoice = self._create_invoice(due_date)

        wizard = self.env["pre.duedate.reminder"].create(
            {
                "partner_id": self.partner.id,
                "invoice_ids": [(6, 0, [invoice.id])],
                "company_id": self.company.id,
            }
        )
        wizard.generate_mail()

        invoice.invalidate_model()
        self.assertTrue(
            invoice.pre_duedate_reminder_mail_id,
            "The wizard should set pre_duedate_reminder_mail_id on the invoice.",
        )
        mail = invoice.pre_duedate_reminder_mail_id
        self.assertEqual(mail.res_id, self.partner.id)
        self.assertEqual(mail.model, "res.partner")
        self.assertTrue(
            mail.attachment_ids,
            "The wizard should attach the invoice PDF to the mail.",
        )
