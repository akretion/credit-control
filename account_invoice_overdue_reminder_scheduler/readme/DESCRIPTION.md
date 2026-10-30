This module adds an automatic sending of the overdue customer invoice
reminders by e-mail: a daily scheduled action runs the wizard of the module
*Overdue Invoice Reminder* and validates it, so that the reminders are sent
without any manual action.

The automatic sending only handles the reminders by e-mail: letters and phone
calls always require a manual action.

When an automatic reminder cannot be sent (missing e-mail address on the
contact to remind, broken reminder e-mail template, error while generating the
invoice PDF, etc.), an alert e-mail is sent for that customer, using the mail
template *Overdue Invoice Reminder Alert*: the recipients are configured on
that template. There is no alert when there is simply nothing to remind, and a
failure of the wizard itself is not hidden: it fails the scheduled action, so
that the problem is fixed quickly.
