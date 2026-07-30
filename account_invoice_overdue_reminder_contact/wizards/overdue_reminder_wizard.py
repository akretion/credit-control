# Copyright 2020-2021 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class OverdueReminderStart(models.TransientModel):
    _inherit = "overdue.reminder.start"

    def _get_reminder_contact(
        self,
        commercial_partner,
    ):
        partner_id = super()._get_reminder_contact(commercial_partner)
        if self.partner_policy == "dunning_contact":
            partner_id = commercial_partner.address_get(["dunning"])["dunning"]
        return partner_id
