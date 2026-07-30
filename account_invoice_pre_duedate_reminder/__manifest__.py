# Copyright 2021 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Invoice Pre Due Date Reminder",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "license": "AGPL-3",
    "summary": " invoice reminder ",
    "author": "Akretion,Odoo Community Association (OCA)",
    "maintainers": ["bguillot"],
    "website": "https://github.com/OCA/credit-control",
    "depends": ["account", "account_dunning_contact"],
    "data": [
        "data/data.xml",
        "security/ir.model.access.csv",
        "views/account_config_settings.xml",
        "views/account_invoice.xml",
        "views/res_partner.xml",
    ],
    "installable": True,
    "application": False,
}
