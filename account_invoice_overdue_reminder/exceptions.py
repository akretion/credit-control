# Copyright 2026 Akretion France (http://www.akretion.com/)
# @author Benoît Guillot <benoit.guillot@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError


class OverdueReminderNothingToDo(UserError):
    """No customer to remind: this is the normal case, not an error.

    It is raised by the start wizard and must be caught by the callers which
    chain the wizard (a scheduled action for example) to skip it.
    """
