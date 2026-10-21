# Copyright 2020 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    pre_duedate_reminder_interval_days = fields.Char(
        string="Default Pre Due Date Reminder Delays",
        help="Delay(s) in days before the invoice due date, separated by "
        "commas: for example '10,5' sends a reminder 10 days before the due "
        "date and another one 5 days before the due date. Leave empty to "
        "disable the feature.",
    )

    @api.constrains("pre_duedate_reminder_interval_days")
    def _check_pre_duedate_reminder_interval_days(self):
        for company in self:
            value = company.pre_duedate_reminder_interval_days
            if value and not re.fullmatch(r"\s*\d+(\s*,\s*\d+)*\s*", value):
                raise ValidationError(
                    _(
                        "The reminder delays must be positive integer numbers "
                        "of days, separated by commas, for example '10,5'."
                    )
                )

    def _get_pre_duedate_reminder_delays(self):
        """Return the reminder delays in days, sorted from the biggest one.

        The delays are relative to the due date: a delay of 10 means 'remind
        the customer 10 days before the due date'.
        """
        self.ensure_one()
        if not self.pre_duedate_reminder_interval_days:
            return []
        delays = [
            int(delay.strip())
            for delay in self.pre_duedate_reminder_interval_days.split(",")
            if delay.strip()
        ]
        # a delay of 0 day doesn't make sense: it would be a reminder for an
        # invoice that is not due yet, which is never selected
        return sorted({delay for delay in delays if delay > 0}, reverse=True)
