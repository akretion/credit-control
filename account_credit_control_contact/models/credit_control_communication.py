# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class CreditControlCommunication(models.Model):
    _inherit = "credit.control.communication"

    @api.model
    def _onchange_partner_id(self):
        """Update address when partner changes."""
        for one in self:
            partners = one.env["res.partner"].search(
                [("id", "child_of", one.partner_id.id)]
            )
            if one.contact_address_id in partners:
                # Contact is already child of partner
                return
            address_ids = one.partner_id.address_get(adr_pref=["credit_control"])
            one.contact_address_id = address_ids["credit_control"]
