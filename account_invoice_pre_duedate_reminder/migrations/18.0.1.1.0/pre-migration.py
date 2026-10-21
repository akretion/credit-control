# Copyright 2026 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_name = 'res_company'
          AND column_name = 'pre_duedate_reminder_interval_days'
        """
    )
    res = cr.fetchone()
    if res and res[0] != "character varying":
        # the field was an integer (days before the due date); it now holds a
        # list of delays, so convert the column and keep the existing value
        logger.info(
            "Converting column res_company.pre_duedate_reminder_interval_days "
            "to varchar"
        )
        cr.execute(
            """
            ALTER TABLE res_company
            ALTER COLUMN pre_duedate_reminder_interval_days TYPE varchar
            USING pre_duedate_reminder_interval_days::varchar
            """
        )
