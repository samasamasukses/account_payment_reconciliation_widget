# ============================================================================
# ACCOUNT PAYMENT MODEL EXTENSION
# ============================================================================
# models/account_payment.py

from odoo import models, fields, api, _


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    reconcile_move_line_count = fields.Integer(
        string='Reconcilable Move Lines',
        compute='_compute_reconcile_move_line_count'
    )

    bank_reference = fields.Char(copy=False)
    cheque_reference = fields.Char(copy=False)
    effective_date = fields.Date('Effective Date',
                                 help='Effective date of PDC', copy=False,
                                 default=False)

    @api.depends('move_id', 'move_id.line_ids', 'state', 'partner_id')
    def _compute_reconcile_move_line_count(self):
        for payment in self:
            if payment.state in ('posted') and payment.move_id and payment.partner_id:
                domain = [
                    ('account_id.reconcile', '=', True),
                    ('reconciled', '=', False),
                    ('partner_id', '=', payment.partner_id.id),
                    ('move_id', '!=', payment.move_id.id)
                ]

                if payment.payment_type == 'inbound':
                    domain.append(('account_id.account_type', '=', 'asset_receivable'))
                else:
                    domain.append(('account_id.account_type', '=', 'liability_payable'))

                payment.reconcile_move_line_count = len(self.env['account.move.line'].search(domain))
            else:
                payment.reconcile_move_line_count = 0

    def action_open_reconcile_widget(self):
        """Open the reconciliation widget for this payment"""
        self.ensure_one()

        if self.state != 'posted':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'message': _('You can only reconcile posted payments.'),
                    'type': 'warning',
                }
            }

        return {
            'name': _('Payment Reconciliation'),
            'type': 'ir.actions.act_window',
            'res_model': 'payment.reconcile.widget',
            'view_mode': 'form',
            'view_id': self.env.ref('account_payment_reconciliation_widget.payment_reconcile_widget_view_form').id,
            'target': 'current',
            'context': {
                'default_payment_id': self.id,
                'payment_reconcile': True,
            }
        }
