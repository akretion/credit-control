# Copyright 2020 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    pre_duedate_reminder_interval_days = fields.Integer(
        string="Default Pre Due Date Reminder Interval (days)",
        default=0,
        help="To activate this feature, set interval over 0.",
    )
