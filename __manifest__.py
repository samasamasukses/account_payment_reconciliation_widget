{
    'name': 'Account Payment Manual Reconciliation Widget',
    'version': '16.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Manual reconciliation widget for account payments',
    'description': """
Account Payment Manual Reconciliation Widget
===========================================

This module adds a manual reconciliation widget for account payments similar to account_reconcile_oca
but specifically designed for account.payment records.

Features:
* Smart button on account.payment form view
* Manual reconciliation widget view (not wizard)
* Reconcile payment with related move lines
* Real-time balance calculation
* Keyboard shortcuts support
* Based on account_reconcile_oca structure
    """,
    'author': 'Your Company',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_payment_views.xml',
        'views/payment_reconcile_widget_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'account_payment_reconciliation_widget/static/src/css/payment_reconcile_widget.css',
            'account_payment_reconciliation_widget/static/src/xml/payment_reconcile_templates.xml',
            'account_payment_reconciliation_widget/static/src/js/payment_reconcile_widget.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}