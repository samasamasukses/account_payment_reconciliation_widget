# ============================================================================
# PAYMENT RECONCILE WIDGET MODEL
# ============================================================================
# models/payment_reconcile_widget.py

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PaymentReconcileWidget(models.TransientModel):
    _name = 'payment.reconcile.widget'
    _description = 'Direct Payment Reconciliation Widget'

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
        readonly=True
    )

    reconcile_account_id = fields.Many2one(
        'account.account',
        string='Reconcile Account',
        compute='_compute_reconcile_account',
        store=True
    )

    payment_balance = fields.Monetary(
        string='Payment Balance',
        compute='_compute_payment_balance',
        currency_field='currency_id'
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='payment_id.currency_id',
        readonly=True
    )

    available_line_ids = fields.Many2many(
        'account.move.line',
        string='Available Lines for Reconciliation',
        compute='_compute_available_lines'
    )

    selected_line_ids = fields.Many2many(
        'account.move.line',
        'payment_reconcile_selected_lines',
        string='Selected Lines'
    )

    @api.depends('payment_id', 'payment_id.move_id')
    def _compute_reconcile_account(self):
        """Find the main reconcile account from payment"""
        for record in self:
            account = False
            if record.payment_id and record.payment_id.move_id:
                account = self._get_payment_reconcile_account(record.payment_id)
            record.reconcile_account_id = account

    @api.depends('payment_id', 'reconcile_account_id')
    def _compute_payment_balance(self):
        """Compute the balance of payment lines in reconcile account"""
        for record in self:
            balance = 0.0
            if record.payment_id and record.reconcile_account_id:
                payment_lines = record.payment_id.move_id.line_ids.filtered(
                    lambda l: l.account_id == record.reconcile_account_id and not l.reconciled
                )
                balance = sum(payment_lines.mapped('balance'))
            record.payment_balance = balance

    @api.depends('payment_id', 'reconcile_account_id', 'partner_id')
    def _compute_available_lines(self):
        """Find available lines for reconciliation from same account"""
        for record in self:
            lines = self.env['account.move.line']
            if record.reconcile_account_id and record.partner_id and record.payment_id:
                domain = [
                    ('account_id', '=', record.reconcile_account_id.id),
                    ('partner_id', '=', record.partner_id.id),
                    ('reconciled', '=', False),
                    ('move_id', '!=', record.payment_id.move_id.id)
                ]
                lines = self.env['account.move.line'].search(domain, limit=100)
            record.available_line_ids = lines

    def _get_payment_reconcile_account(self, payment):
        """Get the main reconcile account from payment"""
        if not payment or not payment.move_id:
            return False

        # Get all reconcilable unreconciled lines
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

    @api.model
    def default_get(self, fields_list):
        """Set default values"""
        res = super().default_get(fields_list)
        payment_id = self.env.context.get('default_payment_id')

        if payment_id:
            res['payment_id'] = payment_id

        return res

    def action_reconcile_selected(self):
        """Reconcile payment with selected lines"""
        self.ensure_one()

        if not self.selected_line_ids:
            raise UserError(_("Please select at least one line to reconcile."))

        if not self.reconcile_account_id:
            raise UserError(_("No reconcile account found for this payment."))

        # Get payment lines from reconcile account
        payment_lines = self.payment_id.move_id.line_ids.filtered(
            lambda l: l.account_id == self.reconcile_account_id and not l.reconciled
        )

        if not payment_lines:
            raise UserError(_("No unreconciled payment lines found."))

        # Validate selected lines are from same account
        wrong_account_lines = self.selected_line_ids.filtered(
            lambda l: l.account_id != self.reconcile_account_id
        )
        if wrong_account_lines:
            raise UserError(_(
                "Some selected lines are not from the reconcile account (%s)"
            ) % self.reconcile_account_id.name)

        # Combine lines
        all_lines = payment_lines | self.selected_line_ids

        # Check balance
        total_balance = sum(all_lines.mapped('balance'))
        if abs(total_balance) > 0.01:
            raise UserError(_(
                "Reconciliation is not balanced. Total balance: %.2f"
            ) % total_balance)

        # Perform reconciliation
        try:
            all_lines.reconcile()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Reconciliation completed successfully!'),
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(_("Reconciliation failed: %s") % str(e))

    def action_auto_reconcile(self):
        """Attempt automatic reconciliation"""
        self.ensure_one()

        if not self.reconcile_account_id:
            raise UserError(_("No reconcile account found for this payment."))

        # Get payment lines
        payment_lines = self.payment_id.move_id.line_ids.filtered(
            lambda l: l.account_id == self.reconcile_account_id and not l.reconciled
        )

        if not payment_lines:
            raise UserError(_("No payment lines to reconcile."))

        payment_balance = sum(payment_lines.mapped('balance'))

        # Find exact match first
        for line in self.available_line_ids:
            if abs(line.balance + payment_balance) < 0.01:
                try:
                    all_lines = payment_lines | line
                    all_lines.reconcile()
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Success'),
                            'message': _('Auto-reconciled with %s') % line.move_id.name,
                            'type': 'success',
                        }
                    }
                except:
                    continue

        # Try combinations
        from itertools import combinations
        lines_list = list(self.available_line_ids)

        for combo_size in range(2, min(6, len(lines_list) + 1)):
            for combo in combinations(lines_list, combo_size):
                combo_balance = sum([l.balance for l in combo])
                if abs(combo_balance + payment_balance) < 0.01:
                    try:
                        all_lines = payment_lines
                        for line in combo:
                            all_lines |= line
                        all_lines.reconcile()
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('Success'),
                                'message': _('Auto-reconciled with %d entries') % len(combo),
                                'type': 'success',
                            }
                        }
                    except:
                        continue

        raise UserError(_("No matching entries found for automatic reconciliation."))

    def action_refresh(self):
        """Refresh the widget data"""
        # Clear selected lines and recompute
        self.selected_line_ids = [(5, 0, 0)]
        self._compute_available_lines()
        self._compute_payment_balance()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Info'),
                'message': _('Data refreshed successfully'),
                'type': 'info',
            }
        }