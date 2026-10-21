# Copyright 2026 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    # invoices that already got a reminder have consumed the first delay of the
    # company: without this, they would get an extra reminder for that delay
    cr.execute(
        """
        UPDATE account_move
        SET pre_duedate_reminder_count = 1
        WHERE pre_duedate_reminder_mail_id IS NOT NULL
          AND COALESCE(pre_duedate_reminder_count, 0) = 0
        """
    )
    logger.info("%s invoices already reminded with a single delay", cr.rowcount)
