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
        """Get reconciliation data for a payment via HTTP route"""
        try:
            _logger.info(f"Getting reconcile data for payment ID: {payment_id}")

            payment = request.env['account.payment'].browse(payment_id)
            if not payment.exists():
                return {'error': 'Payment not found'}

            # Get reconcilable move lines
            domain = [
                ('account_id.reconcile', '=', True),
                ('reconciled', '=', False),
                ('partner_id', '=', payment.partner_id.id),
                ('move_id', '!=', payment.move_id.id if payment.move_id else False)
            ]

            # Include outstanding receivable/payable lines
            if payment.payment_type == 'inbound':
                domain.append(('account_id.account_type', '=', 'asset_receivable'))
            else:
                domain.append(('account_id.account_type', '=', 'liability_payable'))

            reconcilable_lines = request.env['account.move.line'].search(domain, limit=50)

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
                },
                'payment_move_lines': [],
                'reconcilable_lines': [],
            }

            # Get payment move lines
            if payment.move_id:
                for line in payment.move_id.line_ids.filtered(lambda l: l.account_id.reconcile and not l.reconciled):
                    data['payment_move_lines'].append({
                        'id': line.id,
                        'name': line.name or line.move_id.name,
                        'account_id': line.account_id.id,
                        'account_name': line.account_id.name,
                        'debit': line.debit,
                        'credit': line.credit,
                        'balance': line.debit - line.credit,
                        'amount_currency': line.amount_currency,
                        'currency_id': line.currency_id.id if line.currency_id else False,
                        'date': line.date.strftime('%Y-%m-%d') if line.date else '',
                    })

            # Get reconcilable move lines
            for line in reconcilable_lines:
                data['reconcilable_lines'].append({
                    'id': line.id,
                    'name': line.name or line.move_id.name,
                    'account_id': line.account_id.id,
                    'account_name': line.account_id.name,
                    'debit': line.debit,
                    'credit': line.credit,
                    'balance': line.debit - line.credit,
                    'amount_currency': line.amount_currency,
                    'currency_id': line.currency_id.id if line.currency_id else False,
                    'date': line.date.strftime('%Y-%m-%d') if line.date else '',
                    'ref': line.move_id.ref or '',
                    'move_name': line.move_id.name,
                })

            _logger.info(
                f"Returning data: {len(data['payment_move_lines'])} payment lines, {len(data['reconcilable_lines'])} reconcilable lines")
            return data

        except Exception as e:
            _logger.error(f"Error getting reconcile data: {str(e)}", exc_info=True)
            return {'error': str(e)}

    @http.route('/payment_reconcile/reconcile', type='json', auth='user', methods=['POST'])
    def reconcile_lines(self, payment_id, selected_line_ids):
        """Perform reconciliation via HTTP route"""
        try:
            _logger.info(f"Reconciling payment {payment_id} with lines {selected_line_ids}")

            payment = request.env['account.payment'].browse(payment_id)
            if not payment.exists():
                return {'error': 'Payment not found'}

            # Get payment move lines
            payment_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_id.reconcile and not l.reconciled
            )

            if not payment_lines:
                return {'error': 'No unreconciled payment lines found'}

            # Get selected move lines
            selected_lines = request.env['account.move.line'].browse(selected_line_ids)

            # Combine lines for reconciliation
            lines_to_reconcile = payment_lines + selected_lines

            # Check if reconciliation is balanced
            total_debit = sum(lines_to_reconcile.mapped('debit'))
            total_credit = sum(lines_to_reconcile.mapped('credit'))

            if abs(total_debit - total_credit) > 0.01:  # Allow small rounding differences
                return {
                    'error': f'The reconciliation is not balanced. Total debit: {total_debit}, Total credit: {total_credit}'}

            # Perform reconciliation
            lines_to_reconcile.reconcile()

            _logger.info(f"Successfully reconciled {len(lines_to_reconcile)} lines")
            return {'success': True, 'message': 'Reconciliation completed successfully'}

        except Exception as e:
            _logger.error(f"Error performing reconciliation: {str(e)}", exc_info=True)
            return {'error': str(e)}