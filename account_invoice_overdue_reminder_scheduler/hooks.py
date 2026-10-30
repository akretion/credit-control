# Copyright 2026 Akretion France (http://www.akretion.com/)
# @author Benoît Guillot <benoit.guillot@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

_logger = logging.getLogger(__name__)

REMINDER_TEMPLATE_XMLID = (
    "account_invoice_overdue_reminder.overdue_invoice_reminder_mail_template"
)


def _credit_note_table(env):
    """QWeb source of the table of the unreconciled credit notes, in the
    language of ``env``.

    The body of a mail template is a translated field: the source of the table
    has to be written in the body of each active language, that is why its texts
    are translated here instead of being part of a data file.
    """
    return f"""
<t
    t-set="credit_note_moves"
    t-value="object._get_unreconciled_credit_note_moves()"
/>
<t t-if="credit_note_moves">
    <p
    >{env._("The following credit notes of your account are not reconciled:")}</p>

    <table
  style="border-spacing: 0; border-collapse: collapse; width: 100%; text-align: center;"
    >
        <tr>
            <th
                style="padding: 5px; border: 1px solid black;"
            >{env._("Credit Note Number")}</th>
            <th
                style="padding: 5px; border: 1px solid black;"
            >{env._("Date")}</th>
            <th
                style="padding: 5px; border: 1px solid black;"
            >{env._("Due Date")}</th>
            <th
                style="padding: 5px; border: 1px solid black;"
            >{env._("Total")}</th>
            <th
                style="padding: 5px; border: 1px solid black;"
            >{env._("Residual")}</th>
        </tr>
        <t
            t-foreach="credit_note_moves.sorted(key='invoice_date')"
            t-as="credit_note"
        >
            <tr>
                <td style="padding: 5px; border: 1px solid black;">
                    <t t-out="credit_note.name" />
                </td>
                <td style="padding: 5px; border: 1px solid black;">
                    <t t-out="credit_note.invoice_date" />
                </td>
                <td style="padding: 5px; border: 1px solid black;">
                    <t t-out="credit_note.invoice_date_due" />
                </td>
                <td
                    style="padding: 5px; border: 1px solid black; text-align: right;"
                >
                    <t
                t-out="format_amount(credit_note.amount_total, credit_note.currency_id)"
                    />
                </td>
                <td
                    style="padding: 5px; border: 1px solid black; text-align: right;"
                >
                    <t
             t-out="format_amount(credit_note.amount_residual, credit_note.currency_id)"
                    />
                </td>
            </tr>
        </t>
    </table>
</t>
"""


def _insert_credit_note_table(body, table):
    """Insert the credit notes table after the table of the overdue invoices."""
    body = str(body)  # body is a Markup: str() avoids escaping the table
    position = body.find("</table>")
    if position == -1:
        return False
    position += len("</table>")
    return body[:position] + table + body[position:]


def post_init_hook(env):
    """Add the table of the unreconciled credit notes to the other languages.

    The body of the mail template *Overdue Invoice Reminder* is defined, in the
    source language, by ``data/mail_template.xml``: this module extends it with a
    table listing the unreconciled credit notes of the customer, in a separate
    block that the recipients can keep or remove before sending the reminder.
    That data record is only written at installation, so a later modification of
    the template by the user is never overwritten.

    The body of a mail template is also stored per language: the translated
    bodies come from the (translated) mail template of the module 'Overdue
    Invoice Reminder', which has no table, so this hook adds the block to the
    body of every language active at installation.
    """
    template = env.ref(REMINDER_TEMPLATE_XMLID, raise_if_not_found=False)
    if not template:
        _logger.warning("Mail template %s not found", REMINDER_TEMPLATE_XMLID)
        return
    lang_codes = [
        code
        for code in env["res.lang"].search([("active", "=", True)]).mapped("code")
        if code != "en_US"
    ]
    translations = {}
    for code in lang_codes:
        body = template.with_context(lang=code).body_html or ""
        if "credit_note_moves" in body:
            # already in the body of that language
            continue
        new_body = _insert_credit_note_table(
            body, _credit_note_table(env(context=dict(env.context, lang=code)))
        )
        if not new_body:
            _logger.warning(
                "No table found in the body of the mail template %s in the "
                "language %s: the table of the credit notes is not added",
                REMINDER_TEMPLATE_XMLID,
                code,
            )
            continue
        translations[code] = new_body
    if translations:
        # a translated field cannot be written language per language with write():
        # the last write would replace the value of every language
        template.update_field_translations("body_html", translations)
