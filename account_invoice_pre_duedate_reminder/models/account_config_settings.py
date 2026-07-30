# Copyright 2020 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pre_duedate_reminder_interval_days = fields.Integer(
        related="company_id.pre_duedate_reminder_interval_days", readonly=False
    )
