# Copyright 2026 Akretion France (http://www.akretion.com/)
# @author Benoît Guillot <benoit.guillot@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    overdue_reminder_auto_send = fields.Boolean(
        string="Automatic Overdue Reminder Sending",
        help="If enabled, the overdue reminders are sent automatically by "
        "e-mail by the scheduled action 'Overdue Invoice Reminder: automatic "
        "sending'. The trigger delay and the minimum delay since last "
        "reminder configured above are used to select the invoices to remind.",
    )
