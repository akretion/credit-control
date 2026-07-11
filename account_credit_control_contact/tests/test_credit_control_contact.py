# Copyright 2024 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.tests import tagged

from odoo.addons.base.tests.common import BaseCommon


@tagged("post_install", "-at_install")
class TestCreditControlContact(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Setup account
        cls.account_receivable = cls.env["account.account"].create(
            {
                "code": "400001",
                "name": "Test Receivable",
                "account_type": "asset_receivable",
                "reconcile": True,
            }
        )
        # Setup credit control policy
        cls.credit_policy = cls.env.ref("account_credit_control.credit_control_3_time")
        cls.credit_policy.write({"account_ids": [(6, 0, [cls.account_receivable.id])]})

        cls.company = cls.env["res.partner"].create(
            {
                "name": "Test Company",
                "is_company": True,
                "email": "company@example.com",
                "property_account_receivable_id": cls.account_receivable.id,
                "credit_policy_id": cls.credit_policy.id,
            }
        )
        cls.env["res.partner"].create(
            {
                "name": "Credit Control Contact",
                "is_company": False,
                "parent_id": cls.company.id,
                "type": "credit_control",
                "email": "credit-control@example.com",
            }
        )

    def test_onchange_partner_id_sets_credit_control_contact(self):
        """
        Test that _onchange_partner_id sets contact_address_id to credit_control
        contact.
        """
        Communication = self.env["credit.control.communication"]
        credit_control_contact = self.env["res.partner"].search(
            [("parent_id", "=", self.company.id), ("type", "=", "credit_control")]
        )
        comm = Communication.new({"partner_id": self.company.id})
        comm._onchange_partner_id()
        self.assertEqual(comm.contact_address_id, credit_control_contact)

    def test_onchange_partner_id_fallback_to_company(self):
        """
        Test that _onchange_partner_id falls back to company if no credit_control
        contact.
        """
        company_no_cc = self.env["res.partner"].create(
            {
                "name": "Company No CC",
                "is_company": True,
                "email": "no-cc-company@example.com",
                "property_account_receivable_id": self.account_receivable.id,
                "credit_policy_id": self.credit_policy.id,
            }
        )
        Communication = self.env["credit.control.communication"]
        comm = Communication.new({"partner_id": company_no_cc.id})
        comm._onchange_partner_id()
        self.assertEqual(comm.contact_address_id, company_no_cc)

    def test_get_emailing_contact_with_credit_control_email(self):
        """
        Test that get_emailing_contact returns credit_control contact when it has email.
        """
        Communication = self.env["credit.control.communication"]
        comm = Communication.create({"partner_id": self.company.id})
        comm._onchange_partner_id()
        emailing_contact = comm.get_emailing_contact()
        self.assertEqual(emailing_contact.email, "credit-control@example.com")

    def test_get_emailing_contact_fallback_to_parent(self):
        """
        Test that get_emailing_contact falls back to parent when credit_control has no
        email.
        """
        company_no_email_cc = self.env["res.partner"].create(
            {
                "name": "Company No Email CC",
                "is_company": True,
                "email": "company-no-email-cc@example.com",
                "property_account_receivable_id": self.account_receivable.id,
                "credit_policy_id": self.credit_policy.id,
            }
        )
        self.env["res.partner"].create(
            {
                "name": "CC No Email",
                "is_company": False,
                "parent_id": company_no_email_cc.id,
                "type": "credit_control",
                "email": False,
            }
        )
        Communication = self.env["credit.control.communication"]
        comm = Communication.create({"partner_id": company_no_email_cc.id})
        comm._onchange_partner_id()
        emailing_contact = comm.get_emailing_contact()
        self.assertEqual(emailing_contact, company_no_email_cc)
        self.assertEqual(emailing_contact.email, "company-no-email-cc@example.com")

    def test_get_email_returns_credit_control_email(self):
        """Test that get_email returns the credit_control contact email."""
        Communication = self.env["credit.control.communication"]
        comm = Communication.create({"partner_id": self.company.id})
        comm._onchange_partner_id()
        email = comm.get_email()
        self.assertEqual(email, "credit-control@example.com")

    def test_get_email_fallback_to_parent_email(self):
        """
        Test that get_email falls back to parent email when credit_control has no email.
        """
        Communication = self.env["credit.control.communication"]
        # Create a company with only a credit_control contact without email
        company2 = self.env["res.partner"].create(
            {
                "name": "Company 2",
                "is_company": True,
                "email": "company2@example.com",
                "property_account_receivable_id": self.account_receivable.id,
                "credit_policy_id": self.credit_policy.id,
            }
        )
        self.env["res.partner"].create(
            {
                "name": "CC No Email",
                "is_company": False,
                "parent_id": company2.id,
                "type": "credit_control",
                "email": False,
            }
        )
        comm = Communication.create({"partner_id": company2.id})
        comm._onchange_partner_id()
        email = comm.get_email()
        self.assertEqual(email, "company2@example.com")
