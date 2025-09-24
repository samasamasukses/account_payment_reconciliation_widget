# ============================================================================
# PAYMENT RECONCILE CONTROLLER
# ============================================================================
# controllers/payment_reconcile_controller.py

from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class PaymentReconcileController(http.Controller):

    @http.route('/payment_reconcile/get_data', type='json', auth='user', methods=['POST'])
    def get_reconcile_data(self, payment_id):
        """Get reconciliation data for a payment - same account only"""
        try:
            _logger.info(f"Getting reconcile data for payment ID: {payment_id}")

            payment = request.env['account.payment'].browse(payment_id)
            if not payment.exists():
                return {'error': 'Payment not found'}

            if not payment.move_id:
                return {'error': 'Payment has no journal entry'}

            # Find the main reconciliation account from payment
            reconcile_account = self._get_payment_reconcile_account(payment)
            if not reconcile_account:
                return {'error': 'No reconcilable account found in payment'}

            # Get unreconciled payment lines from this account
            payment_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id == reconcile_account and not l.reconciled
            )

            if not payment_lines:
                return {'error': 'No unreconciled lines found in payment for reconciliation'}

            # Find other unreconciled lines from the same account and partner
            domain = [
                ('account_id', '=', reconcile_account.id),
                ('partner_id', '=', payment.partner_id.id),
                ('reconciled', '=', False),
                ('move_id', '!=', payment.move_id.id)
            ]

            other_lines = request.env['account.move.line'].search(domain, limit=100)

            data = {
                'payment': {
                    'id': payment.id,
                    'name': payment.name,
                    'amount': payment.amount,
                    'currency_id': payment.currency_id.id,
                    'currency_symbol': payment.currency_id.symbol,
                    'partner_id': payment.partner_id.id,
                    'partner_name': payment.partner_id.name,
                    'payment_type': payment.payment_type,
                    'date': payment.date.strftime('%Y-%m-%d') if payment.date else '',
                    'reconcile_account_id': reconcile_account.id,
                    'reconcile_account_name': reconcile_account.name,
                },
                'payment_move_lines': [],
                'reconcilable_lines': [],
            }

            # Add payment lines
            for line in payment_lines:
                data['payment_move_lines'].append({
                    'id': line.id,
                    'name': line.name or line.move_id.name,
                    'account_id': line.account_id.id,
                    'account_name': line.account_id.name,
                    'debit': line.debit,
                    'credit': line.credit,
                    'balance': line.balance,
                    'amount_currency': line.amount_currency,
                    'currency_id': line.currency_id.id if line.currency_id else False,
                    'date': line.date.strftime('%Y-%m-%d') if line.date else '',
                })

            # Add other reconcilable lines from same account
            for line in other_lines:
                data['reconcilable_lines'].append({
                    'id': line.id,
                    'name': line.name or line.move_id.name,
                    'account_id': line.account_id.id,
                    'account_name': line.account_id.name,
                    'debit': line.debit,
                    'credit': line.credit,
                    'balance': line.balance,
                    'amount_currency': line.amount_currency,
                    'currency_id': line.currency_id.id if line.currency_id else False,
                    'date': line.date.strftime('%Y-%m-%d') if line.date else '',
                    'ref': line.move_id.ref or '',
                    'move_name': line.move_id.name,
                })

            _logger.info(
                f"Found {len(data['payment_move_lines'])} payment lines and {len(data['reconcilable_lines'])} reconcilable lines from account {reconcile_account.name}")
            return data

        except Exception as e:
            _logger.error(f"Error getting reconcile data: {str(e)}", exc_info=True)
            return {'error': str(e)}

    def _get_payment_reconcile_account(self, payment):
        """Get the main reconcilable account from payment move"""
        # Priority order for finding reconcile account:
        # 1. Outstanding payments/receipts account
        # 2. Receivable/Payable account
        # 3. Any reconcilable account

        reconcile_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.reconcile and not l.reconciled
        )

        if not reconcile_lines:
            return False

        # Look for outstanding payment/receipt account first
        outstanding_account = False
        if payment.payment_type == 'inbound':
            outstanding_account = payment.company_id.account_journal_outstanding_receipt_id
        else:
            outstanding_account = payment.company_id.account_journal_outstanding_payment_id

        if outstanding_account:
            outstanding_line = reconcile_lines.filtered(
                lambda l: l.account_id == outstanding_account
            )
            if outstanding_line:
                return outstanding_account

        # Look for receivable/payable account
        if payment.payment_type == 'inbound':
            account_type = 'asset_receivable'
        else:
            account_type = 'liability_payable'

        receivable_payable = reconcile_lines.filtered(
            lambda l: l.account_id.account_type == account_type
        )
        if receivable_payable:
            return receivable_payable[0].account_id

        # Return first reconcilable account
        return reconcile_lines[0].account_id

    @http.route('/payment_reconcile/reconcile', type='json', auth='user', methods=['POST'])
    def reconcile_lines(self, payment_id, selected_line_ids):
        """Perform direct reconciliation - same account guaranteed"""
        try:
            _logger.info(f"Direct reconciling payment {payment_id} with lines {selected_line_ids}")

            payment = request.env['account.payment'].browse(payment_id)
            if not payment.exists():
                return {'error': 'Payment not found'}

            # Get reconcile account
            reconcile_account = self._get_payment_reconcile_account(payment)
            if not reconcile_account:
                return {'error': 'No reconcilable account found'}

            # Get payment lines from reconcile account
            payment_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id == reconcile_account and not l.reconciled
            )

            if not payment_lines:
                return {'error': 'No unreconciled payment lines found in reconcile account'}

            # Get selected lines - ensure they're from same account
            selected_lines = request.env['account.move.line'].browse(selected_line_ids).filtered(
                lambda l: l.account_id == reconcile_account and not l.reconciled
            )

            if not selected_lines:
                return {'error': 'No valid selected lines from the same account'}

            # Combine all lines for reconciliation
            all_lines = payment_lines | selected_lines

            # Final validation - all lines must be from same account
            if len(all_lines.mapped('account_id')) != 1:
                return {'error': 'Internal error: Lines from different accounts detected'}

            # Check balance
            total_balance = sum(all_lines.mapped('balance'))
            if abs(total_balance) > 0.01:
                return {
                    'error': f'Reconciliation not balanced. Total balance: {total_balance:.2f}'
                }

            # Perform reconciliation using Odoo's method
            try:
                # Use the reconcile method directly
                reconcile_result = all_lines.reconcile()

                # Check if partial reconciliation was created
                if reconcile_result and 'partial_reconcile_ids' in reconcile_result:
                    _logger.info("Partial reconciliation created")

                # Check if full reconciliation was achieved
                reconciled_lines = all_lines.filtered('reconciled')
                if len(reconciled_lines) == len(all_lines):
                    message = f"Full reconciliation completed for {len(all_lines)} lines"
                else:
                    message = f"Partial reconciliation completed: {len(reconciled_lines)}/{len(all_lines)} lines reconciled"

                _logger.info(message)
                return {'success': True, 'message': message}

            except Exception as reconcile_error:
                _logger.error(f"Reconciliation method failed: {str(reconcile_error)}")
                return {'error': f'Reconciliation failed: {str(reconcile_error)}'}

        except Exception as e:
            _logger.error(f"Error performing reconciliation: {str(e)}", exc_info=True)
            return {'error': str(e)}

    @http.route('/payment_reconcile/auto_reconcile', type='json', auth='user', methods=['POST'])
    def auto_reconcile_payment(self, payment_id):
        """Attempt automatic reconciliation for the payment"""
        try:
            _logger.info(f"Auto reconciling payment {payment_id}")

            payment = request.env['account.payment'].browse(payment_id)
            if not payment.exists():
                return {'error': 'Payment not found'}

            # Get reconcile account
            reconcile_account = self._get_payment_reconcile_account(payment)
            if not reconcile_account:
                return {'error': 'No reconcilable account found'}

            # Get payment lines
            payment_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id == reconcile_account and not l.reconciled
            )

            if not payment_lines:
                return {'error': 'No payment lines to reconcile'}

            # Find matching lines with exact opposite balance
            payment_balance = sum(payment_lines.mapped('balance'))

            # Search for lines that would create a balanced reconciliation
            domain = [
                ('account_id', '=', reconcile_account.id),
                ('partner_id', '=', payment.partner_id.id),
                ('reconciled', '=', False),
                ('move_id', '!=', payment.move_id.id)
            ]

            candidate_lines = request.env['account.move.line'].search(domain)

            # Try to find exact match first
            for line in candidate_lines:
                if abs(line.balance + payment_balance) < 0.01:
                    try:
                        all_lines = payment_lines | line
                        all_lines.reconcile()
                        return {
                            'success': True,
                            'message': f'Auto-reconciled with {line.move_id.name}'
                        }
                    except:
                        continue

            # Try combinations for multiple invoices
            if len(candidate_lines) > 1:
                from itertools import combinations
                for combo_size in range(2, min(6, len(candidate_lines) + 1)):
                    for combo in combinations(candidate_lines, combo_size):
                        combo_balance = sum([l.balance for l in combo])
                        if abs(combo_balance + payment_balance) < 0.01:
                            try:
                                all_lines = payment_lines
                                for line in combo:
                                    all_lines |= line
                                all_lines.reconcile()
                                return {
                                    'success': True,
                                    'message': f'Auto-reconciled with {len(combo)} entries'
                                }
                            except:
                                continue

            return {'error': 'No matching entries found for automatic reconciliation'}

        except Exception as e:
            _logger.error(f"Error in auto reconciliation: {str(e)}", exc_info=True)
            return {'error': str(e)}