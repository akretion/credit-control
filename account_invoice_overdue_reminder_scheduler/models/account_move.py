# Copyright 2026 Akretion France (http://www.akretion.com/)
# @author Benoît Guillot <benoit.guillot@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import api, models

from odoo.addons.account_invoice_overdue_reminder.exceptions import (
    OverdueReminderNothingToDo,
)

logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _overdue_reminder_scheduler(self):
        """Send the overdue reminders automatically (called by a daily cron).

        The 'overdue.reminder.start' wizard is run to generate one
        'overdue.reminder.step' per customer to remind, then each step is
        validated right away: that's the step which really sends the e-mail
        and logs the reminder (history + chatter).

        When a reminder can't be sent (no e-mail on the contact, bad mail
        template, error while generating the invoice PDF, unexpected error),
        an alert e-mail is sent for that customer, using the mail template
        'Overdue Invoice Reminder Alert': its recipients are configured on the
        template. There is no alert when there is simply nothing to remind,
        and a failure of the wizard itself is not caught (it fails the
        scheduled action).
        """
        wizard_model = self.env["overdue.reminder.start"]
        step_model = self.env["overdue.reminder.step"]
        companies = self.env["res.company"].search(
            [("overdue_reminder_auto_send", "=", True)]
        )
        for company in companies:
            # sudo(): the scheduled action may run with a user without the
            # accounting groups. The wizard only works on the company passed
            # in the context, so the scope stays limited to it.
            wizard = (
                wizard_model.sudo()
                .with_company(company)
                .create(
                    {
                        "company_id": company.id,
                        "interface": "mass",
                        "start_days": company.overdue_reminder_start_days,
                        "min_interval_days": company.overdue_reminder_min_interval_days,
                        "partner_policy": company.overdue_reminder_partner_policy,
                    }
                )
            )
            # Only the 'nothing to remind' case is caught: any other error of
            # the wizard is a configuration problem or a bug that must be
            # fixed quickly, so it is left to fail the scheduled action
            # (failure counter, traceback in the log, admin notification)
            # instead of being hidden.
            try:
                wizard.run()
            except OverdueReminderNothingToDo as err:
                # normal case: no customer to remind
                logger.info(
                    "No overdue reminder to send for company %s: %s",
                    company.display_name,
                    err,
                )
                continue
            steps = step_model.sudo().search(
                [
                    ("user_id", "=", self.env.user.id),
                    ("company_id", "=", company.id),
                    ("state", "=", "draft"),
                ]
            )
            for step in steps:
                salesman = step.commercial_partner_id.user_id
                try:
                    with self.env.cr.savepoint():
                        # the reminder is sent by the salesman of the
                        # customer when he has an e-mail address
                        if salesman.email:
                            step.user_id = salesman.id
                        # the error message of a failure is stored on the step
                        # and used in the alert e-mail: it must be in the
                        # language of the company, not in the language of the
                        # user running the scheduled action (often OdooBot)
                        step.with_context(
                            lang=company.partner_id.lang or self.env.lang
                        ).validate()
                except Exception as err:  # noqa: BLE001
                    # one customer must not block the reminders of the others,
                    # but a reminder that could not be sent must be reported
                    logger.warning(
                        "Overdue reminder skipped for customer %s: %s",
                        step.commercial_partner_id.display_name,
                        err,
                    )
                    try:
                        with self.env.cr.savepoint():
                            step.write({"error": str(err)})
                            step.send_alert_mail()
                    except Exception:  # noqa: BLE001
                        logger.exception(
                            "Failed to send the overdue reminder alert for "
                            "customer %s",
                            step.commercial_partner_id.display_name,
                        )
        return True
