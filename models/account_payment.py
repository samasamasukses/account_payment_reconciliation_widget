# ============================================================================
# ACCOUNT PAYMENT MODEL EXTENSION
# ============================================================================
# models/account_payment.py

from odoo import models, fields, api, _
from odoo.exceptions import UserError


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
        """Count reconcilable lines from the same account as payment"""
        for payment in self:
            count = 0
            if payment.state == 'posted' and payment.move_id and payment.partner_id:
                # Find the reconcile account from payment
                reconcile_account = self._get_payment_reconcile_account(payment)

                if reconcile_account:
                    # Count lines from same account and partner
                    domain = [
                        ('account_id', '=', reconcile_account.id),
                        ('partner_id', '=', payment.partner_id.id),
                        ('reconciled', '=', False),
                        ('move_id', '!=', payment.move_id.id)
                    ]
                    count = self.env['account.move.line'].search_count(domain)

            payment.reconcile_move_line_count = count

    def _get_payment_reconcile_account(self, payment):
        """Get the main reconcile account from payment move lines"""
        if not payment or not payment.move_id:
            return False

        # Get reconcilable unreconciled lines
        reconcile_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.reconcile and not l.reconciled
        )

        if not reconcile_lines:
            return False

        # Priority 1: Outstanding payments/receipts account
        company = payment.company_id
        if payment.payment_type == 'inbound':
            outstanding_account = company.account_journal_payment_credit_account_id
        else:
            outstanding_account = company.account_journal_payment_debit_account_id

        if outstanding_account:
            outstanding_line = reconcile_lines.filtered(
                lambda l: l.account_id == outstanding_account
            )
            if outstanding_line:
                return outstanding_account

        # Priority 2: Receivable/Payable account
        account_type = 'asset_receivable' if payment.payment_type == 'inbound' else 'liability_payable'
        partner_account = reconcile_lines.filtered(
            lambda l: l.account_id.account_type == account_type
        )
        if partner_account:
            return partner_account[0].account_id

        # Fallback: First reconcilable account
        return reconcile_lines[0].account_id

    def action_open_reconcile_widget(self):
        """Open the direct reconciliation widget"""
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

        # Check if payment has reconcilable move lines
        reconcile_account = self._get_payment_reconcile_account(self)
        if not reconcile_account:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'message': _('This payment has no reconcilable move lines.'),
                    'type': 'warning',
                }
            }

        # Check if payment lines are already reconciled
        payment_lines = self.move_id.line_ids.filtered(
            lambda l: l.account_id == reconcile_account and not l.reconciled
        )

        if not payment_lines:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Info'),
                    'message': _('This payment is already fully reconciled.'),
                    'type': 'info',
                }
            }

        return {
            'name': _('Direct Payment Reconciliation'),
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

    def action_reconcile_payment_moves(self):
        """Direct method to reconcile payment with specific moves"""
        self.ensure_one()

        reconcile_account = self._get_payment_reconcile_account(self)
        if not reconcile_account:
            raise UserError(_("No reconcilable account found for this payment."))

        # Get unreconciled payment lines
        payment_lines = self.move_id.line_ids.filtered(
            lambda l: l.account_id == reconcile_account and not l.reconciled
        )

        if not payment_lines:
            raise UserError(_("No unreconciled payment lines found."))

        # Find matching lines with opposite balance
        payment_balance = sum(payment_lines.mapped('balance'))

        domain = [
            ('account_id', '=', reconcile_account.id),
            ('partner_id', '=', self.partner_id.id),
            ('reconciled', '=', False),
            ('move_id', '!=', self.move_id.id)
        ]

        candidate_lines = self.env['account.move.line'].search(domain)

        # Try exact match first
        for line in candidate_lines:
            if abs(line.balance + payment_balance) < 0.01:
                try:
                    all_lines = payment_lines | line
                    all_lines.reconcile()
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Success'),
                            'message': _('Payment reconciled with %s') % line.move_id.name,
                            'type': 'success',
                        }
                    }
                except Exception as e:
                    continue

        # No automatic match found
        return self.action_open_reconcile_widget()