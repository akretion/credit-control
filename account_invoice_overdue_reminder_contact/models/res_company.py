# Copyright 2020-2021 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, models


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def _overdue_reminder_partner_policy_selection(self):
        res = super()._overdue_reminder_partner_policy_selection()
        res.append(("dunning_contact", _("Dunning Contact")))
        return res
