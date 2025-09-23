# ============================================================================
# PAYMENT RECONCILE WIDGET MODEL
# ============================================================================
# models/payment_reconcile_widget.py

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PaymentReconcileWidget(models.TransientModel):
    _name = 'payment.reconcile.widget'
    _description = 'Payment Reconciliation Widget'

    payment_id = fields.Many2one(
        'account.payment',
        string='Payment',
        required=True,
        ondelete='cascade'
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        related='payment_id.partner_id',
        store=True
    )

    move_line_ids = fields.Many2many(
        'account.move.line',
        string='Move Lines to Reconcile',
        domain="[('account_id.reconcile', '=', True), ('reconciled', '=', False)]"
    )

    payment_move_line_ids = fields.Many2many(
        'account.move.line',
        relation='payment_reconcile_payment_lines',
        string='Payment Move Lines',
        compute='_compute_payment_move_line_ids',
        store=True
    )

    reconcile_data = fields.Text(
        string='Reconcile Data',
        help='JSON data for the reconciliation widget'
    )

    @api.depends('payment_id', 'payment_id.move_id')
    def _compute_payment_move_line_ids(self):
        for record in self:
            if record.payment_id and record.payment_id.move_id:
                payment_lines = record.payment_id.move_id.line_ids.filtered(
                    lambda line: line.account_id.reconcile and not line.reconciled
                )
                record.payment_move_line_ids = payment_lines
            else:
                record.payment_move_line_ids = False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        payment_id = self.env.context.get('default_payment_id')

        if payment_id:
            payment = self.env['account.payment'].browse(payment_id)
            res['payment_id'] = payment_id

            domain = [
                ('account_id.reconcile', '=', True),
                ('reconciled', '=', False),
                ('partner_id', '=', payment.partner_id.id),
                ('move_id', '!=', payment.move_id.id if payment.move_id else False)
            ]

            if payment.payment_type == 'inbound':
                domain.append(('account_id.account_type', '=', 'asset_receivable'))
            else:
                domain.append(('account_id.account_type', '=', 'liability_payable'))

            move_lines = self.env['account.move.line'].search(domain, limit=50)
            res['move_line_ids'] = [(6, 0, move_lines.ids)]

        return res

    def action_reconcile_lines(self, selected_line_ids):
        """Reconcile selected move lines"""
        self.ensure_one()

        if not selected_line_ids:
            raise UserError(_("Please select move lines to reconcile."))

        payment_lines = self.payment_move_line_ids.filtered(lambda l: not l.reconciled)
        if not payment_lines:
            raise UserError(_("No unreconciled payment lines found."))

        selected_lines = self.env['account.move.line'].browse(selected_line_ids)
        lines_to_reconcile = payment_lines + selected_lines

        total_debit = sum(lines_to_reconcile.mapped('debit'))
        total_credit = sum(lines_to_reconcile.mapped('credit'))

        if abs(total_debit - total_credit) > 0.01:
            raise UserError(_(
                "The reconciliation is not balanced. "
                "Total debit: %s, Total credit: %s"
            ) % (total_debit, total_credit))

        try:
            lines_to_reconcile.reconcile()
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        except Exception as e:
            raise UserError(_("Reconciliation failed: %s") % str(e))

    def action_refresh_data(self):
        """Refresh the reconciliation data"""
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
