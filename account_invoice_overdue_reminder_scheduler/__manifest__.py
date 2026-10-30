# Copyright 2026 Akretion France (http://www.akretion.com/)
# @author Benoît Guillot <benoit.guillot@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Overdue Invoice Reminder Scheduler",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "license": "AGPL-3",
    "summary": "Send the overdue customer invoice reminders automatically",
    "author": "Akretion,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/credit-control",
    "depends": ["account_invoice_overdue_reminder"],
    "data": [
        "wizard/res_config_settings_view.xml",
        "data/ir_cron.xml",
        "data/mail_template.xml",
    ],
    "installable": True,
    "application": False,
}
