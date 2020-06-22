# -*- coding: utf-8 -*-
# Copyright 2020 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountConfigSettings(models.TransientModel):
    _inherit = 'account.config.settings'

    overdue_reminder_attach_invoice = fields.Boolean(
        related='company_id.overdue_reminder_attach_invoice', readonly=False)
    overdue_reminder_start_days = fields.Integer(
        related='company_id.overdue_reminder_start_days', readonly=False)
    overdue_reminder_min_interval_days = fields.Integer(
        related='company_id.overdue_reminder_min_interval_days',
        readonly=False)
    overdue_reminder_interface = fields.Selection(
        related='company_id.overdue_reminder_interface',
        readonly=False)
