/* ============================================================================
 * PAYMENT RECONCILE WIDGET JAVASCRIPT
 * ============================================================================
 * static/src/js/payment_reconcile_widget.js
 */

// Standalone controller that doesn't rely on complex OWL framework
class PaymentReconcileController {
    constructor() {
        this.state = {
            paymentData: {},
            paymentLines: [],
            reconcilableLines: [],
            selectedLines: new Set(),
            summary: {
                debit: 0,
                credit: 0,
                difference: 0
            },
            isLoading: false,
            isReconciling: false
        };

        console.log('PaymentReconcileController initialized');
    }

    async start() {
        console.log('PaymentReconcileController starting...');

        await this.waitForContainer();
        this.enableDebugMode();
        await this.waitForFormLoad();
        await this.initializeWidget();
    }

    async waitForContainer() {
        return new Promise((resolve) => {
            let attempts = 0;
            const maxAttempts = 50;

            const checkContainer = () => {
                attempts++;

                const selectors = [
                    '.payment_reconcile_widget',
                    '#payment_reconcile_main_container',
                    '.payment_reconcile_widget_container',
                    '.o_payment_reconcile_form .payment_reconcile_widget'
                ];

                let container = null;
                for (const selector of selectors) {
                    container = document.querySelector(selector);
                    if (container) {
                        console.log(`✓ Container found with selector: ${selector} (attempt ${attempts})`);
                        break;
                    }
                }

                if (container) {
                    resolve(container);
                } else if (attempts >= maxAttempts) {
                    console.error(`✗ Container not found after ${attempts} attempts`);
                    resolve(null);
                } else {
                    setTimeout(checkContainer, 100);
                }
            };

            checkContainer();
        });
    }

    enableDebugMode() {
        let debugInfo = document.getElementById('debug_info');
        if (!debugInfo) {
            const container = document.querySelector('.payment_reconcile_widget_container, .o_form_sheet');
            if (container) {
                debugInfo = document.createElement('div');
                debugInfo.id = 'debug_info';
                debugInfo.className = 'alert alert-warning';
                debugInfo.innerHTML = `
                    <strong>Debug Info:</strong>
                    <div id="debug_content"></div>
                    <button type="button" class="btn btn-sm btn-secondary mt-2" onclick="this.parentElement.style.display='none'">Hide Debug</button>
                `;
                container.insertBefore(debugInfo, container.firstChild);
            }
        }

        const debugContent = document.getElementById('debug_content');
        if (debugContent) {
            const debugInfo = this.getEnhancedDebugInfo();
            debugContent.innerHTML = debugInfo;
        }
    }

    getEnhancedDebugInfo() {
        let info = `URL: ${window.location.href}<br>`;

        // Enhanced payment field analysis
        info += '<strong>Payment Field Analysis:</strong><br>';

        // Method 1: Check standard form elements
        const standardSelectors = [
            'select[name="payment_id"]',
            'input[name="payment_id"]'
        ];

        standardSelectors.forEach(selector => {
            const element = document.querySelector(selector);
            if (element) {
                info += `${selector}: found, value="${element.value || 'empty'}"<br>`;
            } else {
                info += `${selector}: not found<br>`;
            }
        });

        // Method 2: Check Odoo Many2one widgets
        const many2oneSelectors = [
            '.o_field_many2one[name="payment_id"]',
            '[data-field-name="payment_id"]',
            '.o_field_widget[name="payment_id"]'
        ];

        many2oneSelectors.forEach(selector => {
            const widget = document.querySelector(selector);
            if (widget) {
                info += `${selector}: found<br>`;

                // Check data attributes
                const dataAttrs = ['data-value', 'data-id', 'data-selected-id', 'data-record-id'];
                dataAttrs.forEach(attr => {
                    const value = widget.getAttribute(attr);
                    info += `&nbsp;&nbsp;${attr}: ${value || 'none'}<br>`;
                });

                // Check hidden inputs inside
                const hiddenInputs = widget.querySelectorAll('input[type="hidden"]');
                hiddenInputs.forEach((input, i) => {
                    info += `&nbsp;&nbsp;hidden input ${i}: name="${input.name}" value="${input.value}"<br>`;
                });

                // Check select options
                const selects = widget.querySelectorAll('select');
                selects.forEach((select, i) => {
                    info += `&nbsp;&nbsp;select ${i}: value="${select.value}" options=${select.options.length}<br>`;
                    if (select.selectedIndex >= 0) {
                        const option = select.options[select.selectedIndex];
                        info += `&nbsp;&nbsp;&nbsp;&nbsp;selected: value="${option.value}" text="${option.text}"<br>`;
                    }
                });

                // Check text inputs (for display)
                const textInputs = widget.querySelectorAll('input[type="text"]');
                textInputs.forEach((input, i) => {
                    info += `&nbsp;&nbsp;text input ${i}: value="${input.value}"<br>`;
                });

            } else {
                info += `${selector}: not found<br>`;
            }
        });

        // Method 3: Check all payment-related elements
        const allPaymentElements = document.querySelectorAll('[name*="payment"], [data-field-name*="payment"], [class*="payment"]');
        info += `<strong>All payment-related elements (${allPaymentElements.length}):</strong><br>`;

        allPaymentElements.forEach((element, i) => {
            if (i < 10) { // Limit to first 10 to avoid too much info
                info += `${i}: ${element.tagName}.${element.className} name="${element.name || 'none'}" value="${element.value || 'empty'}"<br>`;
            }
        });

        return info;
    }

    async waitForFormLoad() {
        return new Promise((resolve) => {
            let attempts = 0;
            const maxAttempts = 30;

            const checkForm = () => {
                attempts++;

                // Check if payment field has actual data
                const paymentId = this.extractPaymentIdFromForm();
                console.log(`Form load check ${attempts}: payment ID = ${paymentId}`);

                if (paymentId || attempts >= maxAttempts) {
                    console.log(`Form ready after ${attempts} attempts, payment ID: ${paymentId}`);
                    resolve();
                } else {
                    setTimeout(checkForm, 300);
                }
            };

            checkForm();
        });
    }

    extractPaymentIdFromForm() {
        console.log('=== EXTRACTING PAYMENT ID FROM ODOO FORM ===');

        // Method 1: Hidden input fields (most reliable)
        const hiddenInputs = document.querySelectorAll('input[type="hidden"][name="payment_id"]');
        for (const input of hiddenInputs) {
            if (input.value) {
                const paymentId = parseInt(input.value);
                console.log(`✓ Method 1 - Hidden input: ${paymentId}`);
                return paymentId;
            }
        }

        // Method 2: Many2one widget data attributes
        const many2oneWidgets = document.querySelectorAll('.o_field_many2one[name="payment_id"], [data-field-name="payment_id"]');
        for (const widget of many2oneWidgets) {
            // Check various data attributes where Odoo stores IDs
            const dataAttrs = ['data-value', 'data-id', 'data-selected-id', 'data-record-id'];

            for (const attr of dataAttrs) {
                const value = widget.getAttribute(attr);
                if (value && !isNaN(value)) {
                    const paymentId = parseInt(value);
                    console.log(`✓ Method 2 - Widget ${attr}: ${paymentId}`);
                    return paymentId;
                }
            }

            // Check hidden inputs within the widget
            const hiddenInWidget = widget.querySelectorAll('input[type="hidden"]');
            for (const input of hiddenInWidget) {
                if (input.value && !isNaN(input.value)) {
                    const paymentId = parseInt(input.value);
                    console.log(`✓ Method 2b - Hidden in widget: ${paymentId}`);
                    return paymentId;
                }
            }
        }

        // Method 3: Select options (for select-based widgets)
        const selects = document.querySelectorAll('select[name="payment_id"]');
        for (const select of selects) {
            if (select.value) {
                const paymentId = parseInt(select.value);
                console.log(`✓ Method 3 - Select value: ${paymentId}`);
                return paymentId;
            }

            // Check selected option
            if (select.selectedIndex >= 0) {
                const option = select.options[select.selectedIndex];
                if (option.value && !isNaN(option.value)) {
                    const paymentId = parseInt(option.value);
                    console.log(`✓ Method 3b - Selected option: ${paymentId}`);
                    return paymentId;
                }
            }
        }

        // Method 4: Search in all Many2one widgets for payment_id reference
        const allMany2oneWidgets = document.querySelectorAll('.o_field_many2one');
        for (const widget of allMany2oneWidgets) {
            const fieldName = widget.getAttribute('name') || widget.getAttribute('data-field-name');
            if (fieldName === 'payment_id') {
                // Try to extract from any child element
                const allInputs = widget.querySelectorAll('input, select');
                for (const input of allInputs) {
                    if (input.value && !isNaN(input.value) && parseInt(input.value) > 0) {
                        const paymentId = parseInt(input.value);
                        console.log(`✓ Method 4 - Widget child element: ${paymentId}`);
                        return paymentId;
                    }
                }
            }
        }

        // Method 5: Try Odoo's internal widget data (if accessible)
        if (typeof odoo !== 'undefined') {
            try {
                // Check if we can access the form view's data
                if (odoo.env && odoo.env.model && odoo.env.model.root) {
                    const data = odoo.env.model.root.data;
                    if (data && data.payment_id) {
                        // Handle both single ID and [id, name] format
                        const paymentId = Array.isArray(data.payment_id) ? data.payment_id[0] : data.payment_id;
                        if (paymentId && !isNaN(paymentId)) {
                            console.log(`✓ Method 5 - Odoo model data: ${paymentId}`);
                            return parseInt(paymentId);
                        }
                    }
                }
            } catch (e) {
                console.log(`✗ Method 5 - Odoo data access error: ${e.message}`);
            }
        }

        // Method 6: URL context (last resort)
        const urlParams = new URLSearchParams(window.location.search);
        const contextParam = urlParams.get('context');
        if (contextParam) {
            try {
                const decoded = decodeURIComponent(contextParam);
                const match = decoded.match(/default_payment_id['":\s]*(\d+)/);
                if (match) {
                    const paymentId = parseInt(match[1]);
                    console.log(`✓ Method 6 - URL context: ${paymentId}`);
                    return paymentId;
                }
            } catch (e) {
                console.log(`✗ Method 6 - URL parsing error: ${e.message}`);
            }
        }

        try {
            // Handle Odoo's hash-based routing like #id=123&model=payment.reconcile.widget
            const hash = window.location.hash.substring(1); // Remove the #
            const hashParams = new URLSearchParams(hash);

            // Try different hash parameter names that Odoo might use
            const possibleHashParams = ['active_id', 'id', 'payment_id', 'res_id'];

            for (const param of possibleHashParams) {
                const value = hashParams.get(param);
                if (value && !isNaN(value)) {
                    const paymentId = parseInt(value);
                    console.log(`✓ Method 7 - URL hash ${param}: ${paymentId}`);

                    // Note: This might be the widget ID, not payment ID
                    // But it's worth trying, especially if it's active_id
                    if (param === 'active_id' || param === 'payment_id') {
                        return paymentId;
                    }
                }
            }

            // Also try parsing Odoo's complex hash format
            // Example: #action=123&model=payment.reconcile.widget&view_type=form&id=456
            const actionMatch = hash.match(/action=(\d+)/);
            const modelMatch = hash.match(/model=([^&]+)/);
            const idMatch = hash.match(/[&?]id=(\d+)/);

            if (modelMatch && modelMatch[1].includes('payment') && idMatch) {
                const paymentId = parseInt(idMatch[1]);
                console.log(`✓ Method 7b - Odoo hash action format: ${paymentId}`);
                return paymentId;
            }

        } catch (e) {
            console.log(`✗ Method 7 - Hash parsing error: ${e.message}`);
        }

        console.log('✗ All methods failed to extract payment ID');
        return null;
    }

    async initializeWidget() {
        this.state.isLoading = true;
        await this.loadReconcileData();
        this.setupEventListeners();
        this.state.isLoading = false;
        console.log('PaymentReconcileController ready');
    }

    getPaymentId() {
        // Use the enhanced extraction method
        return this.extractPaymentIdFromForm();
    }

    async loadReconcileData() {
        try {
            const paymentId = this.getPaymentId();
            console.log('Final payment ID for loading data:', paymentId);

            if (!paymentId) {
                const errorMsg = "Cannot extract payment ID from form. Check debug info above.";
                this.showNotification(errorMsg, 'error');
                this.showErrorInContainer('payment_lines_container', 'Payment ID extraction failed');
                this.showErrorInContainer('reconcilable_lines_container', 'Payment ID extraction failed');
                return;
            }

            console.log('Making request to load data for payment:', paymentId);

            const response = await fetch('/payment_reconcile/get_data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: { payment_id: paymentId },
                    id: new Date().getTime()
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log('Response received:', result);

            if (result.error) {
                throw new Error(result.error);
            }

            const data = result.result || {};
            this.state.paymentData = data.payment || {};
            this.state.paymentLines = data.payment_move_lines || [];
            this.state.reconcilableLines = data.reconcilable_lines || [];
            this.state.selectedLines.clear();

            console.log('Data loaded successfully:', {
                payment: this.state.paymentData,
                paymentLines: this.state.paymentLines.length,
                reconcilableLines: this.state.reconcilableLines.length
            });

            this.renderWidget();

        } catch (error) {
            console.error("Error loading reconcile data:", error);
            this.showNotification("Error loading reconciliation data: " + error.message, 'error');
            this.showErrorInContainer('payment_lines_container', 'Failed to load: ' + error.message);
            this.showErrorInContainer('reconcilable_lines_container', 'Failed to load: ' + error.message);
        }
    }

    showErrorInContainer(containerId, message) {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = `
                <div class="alert alert-danger m-3">
                    <i class="fa fa-exclamation-circle"></i>
                    ${message}
                </div>
            `;
        }
    }

    renderWidget() {
        this.renderPaymentLines();
        this.renderReconcilableLines();
        this.updateSummary();
    }

    renderPaymentLines() {
        const container = document.getElementById('payment_lines_container');
        if (!container) return;

        container.innerHTML = '';

        if (this.state.paymentLines.length === 0) {
            container.innerHTML = `
                <div class="alert alert-info m-3">
                    <i class="fa fa-info-circle"></i>
                    No payment lines available for reconciliation
                </div>
            `;
            return;
        }

        this.state.paymentLines.forEach(line => {
            const lineElement = this.createLineElement(line, 'payment');
            container.appendChild(lineElement);
        });
    }

    renderReconcilableLines() {
        const container = document.getElementById('reconcilable_lines_container');
        if (!container) return;

        container.innerHTML = '';

        if (this.state.reconcilableLines.length === 0) {
            container.innerHTML = `
                <div class="alert alert-warning m-3">
                    <i class="fa fa-exclamation-triangle"></i>
                    No reconcilable lines found for this partner
                </div>
            `;
            return;
        }

        this.state.reconcilableLines.forEach(line => {
            const lineElement = this.createLineElement(line, 'reconcilable');
            container.appendChild(lineElement);
        });
    }

    createLineElement(line, type) {
        const div = document.createElement('div');
        div.className = 'reconcile_line';
        div.dataset.lineId = line.id;
        div.dataset.lineType = type;

        const checkbox = type === 'reconcilable' ?
            `<input type="checkbox" class="line_checkbox" data-line-id="${line.id}">` :
            '<span class="line_indicator text-primary">●</span>';

        const balanceClass = line.balance > 0 ? 'text-success' : line.balance < 0 ? 'text-danger' : 'text-muted';
        const currencySymbol = this.state.paymentData.currency_symbol || '';

        div.innerHTML = `
            <div class="d-flex justify-content-between align-items-center p-3 border-bottom hover-bg">
                <div class="d-flex align-items-center">
                    ${checkbox}
                    <div class="ml-3">
                        <strong class="line_name">${line.name || 'Unknown'}</strong>
                        <br>
                        <small class="text-muted">
                            ${line.account_name} | ${line.date}
                            ${line.move_name ? ` | ${line.move_name}` : ''}
                        </small>
                        ${line.ref ? `<br><small class="text-info">Ref: ${line.ref}</small>` : ''}
                    </div>
                </div>
                <div class="text-right">
                    <div class="reconcile_amounts mb-1">
                        <span class="badge badge-light debit">Dr: ${currencySymbol}${line.debit.toFixed(2)}</span>
                        <span class="badge badge-light credit">Cr: ${currencySymbol}${line.credit.toFixed(2)}</span>
                    </div>
                    <div class="balance ${balanceClass} font-weight-bold">
                        Balance: ${currencySymbol}${line.balance.toFixed(2)}
                    </div>
                </div>
            </div>
        `;

        if (type === 'reconcilable') {
            div.style.cursor = 'pointer';
            div.addEventListener('click', (e) => {
                if (e.target.type !== 'checkbox') {
                    const checkbox = div.querySelector('.line_checkbox');
                    if (checkbox) {
                        checkbox.checked = !checkbox.checked;
                        checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
            });
        }

        return div;
    }

    setupEventListeners() {
        console.log('Setting up event listeners...');

        document.addEventListener('change', (event) => {
            if (event.target.classList.contains('line_checkbox')) {
                this.handleLineSelection(event);
            }
        });

        const reconcileBtn = document.getElementById('btn_reconcile');
        if (reconcileBtn) {
            reconcileBtn.addEventListener('click', () => this.performReconciliation());
        }

        const refreshBtn = document.getElementById('btn_refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshData());
        }

        const selectAllBtn = document.getElementById('btn_select_all');
        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', () => this.toggleSelectAll());
        }

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && event.ctrlKey) {
                event.preventDefault();
                this.performReconciliation();
            } else if (event.key === 'F5') {
                event.preventDefault();
                this.refreshData();
            }
        });

        console.log('Event listeners set up successfully');
    }

    handleLineSelection(event) {
        const lineId = parseInt(event.target.dataset.lineId);
        const lineElement = event.target.closest('.reconcile_line');

        if (event.target.checked) {
            this.state.selectedLines.add(lineId);
            lineElement.classList.add('selected');
        } else {
            this.state.selectedLines.delete(lineId);
            lineElement.classList.remove('selected');
        }

        this.updateSummary();
        this.updateReconcileButtonState();
        this.updateSelectAllButton();
    }

    updateSummary() {
        let totalDebit = 0;
        let totalCredit = 0;

        this.state.paymentLines.forEach(line => {
//            totalDebit += line.debit;
            totalCredit += line.credit;
        });

        this.state.reconcilableLines.forEach(line => {
            if (this.state.selectedLines.has(line.id)) {
                totalDebit += line.debit;
                totalCredit += line.credit;
            }
        });

        this.state.summary.debit = totalDebit;
        this.state.summary.credit = totalCredit;
        this.state.summary.difference = totalDebit - totalCredit;

        this.updateSummaryUI();
    }

    updateSummaryUI() {
        const currencySymbol = this.state.paymentData.currency_symbol || '';
        const debitElement = document.getElementById('selected_debit');
        const creditElement = document.getElementById('selected_credit');
        const differenceElement = document.getElementById('balance_difference');

        if (debitElement) debitElement.textContent = `${currencySymbol}${this.state.summary.debit.toFixed(2)}`;
        if (creditElement) creditElement.textContent = `${currencySymbol}${this.state.summary.credit.toFixed(2)}`;
        if (differenceElement) {
            const difference = this.state.summary.difference;
            differenceElement.textContent = `${currencySymbol}${difference.toFixed(2)}`;

            differenceElement.classList.remove('text-success', 'text-danger');
            if (Math.abs(difference) < 0.01) {
                differenceElement.classList.add('text-success');
            } else {
                differenceElement.classList.add('text-danger');
            }
        }
    }

    updateReconcileButtonState() {
        const reconcileBtn = document.getElementById('btn_reconcile');
        if (!reconcileBtn) return;

        const hasSelection = this.state.selectedLines.size > 0;
        const isBalanced = Math.abs(this.state.summary.difference) < 0.01;
        const canReconcile = hasSelection && isBalanced && !this.state.isReconciling;

        reconcileBtn.disabled = !canReconcile;
        reconcileBtn.classList.toggle('btn-success', canReconcile);
        reconcileBtn.classList.toggle('btn-secondary', !canReconcile);

        if (this.state.isReconciling) {
            reconcileBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Reconciling...';
        } else if (isBalanced && hasSelection) {
            reconcileBtn.innerHTML = '<i class="fa fa-check"></i> Reconcile';
        } else if (hasSelection) {
            reconcileBtn.innerHTML = '<i class="fa fa-exclamation-triangle"></i> Not Balanced';
        } else {
            reconcileBtn.innerHTML = '<i class="fa fa-check"></i> Reconcile';
        }
    }

    updateSelectAllButton() {
        const selectAllBtn = document.getElementById('btn_select_all');
        if (!selectAllBtn) return;

        const checkboxes = document.querySelectorAll('.line_checkbox');
        const checkedBoxes = document.querySelectorAll('.line_checkbox:checked');

        if (checkedBoxes.length === 0) {
            selectAllBtn.textContent = 'Select All';
        } else if (checkedBoxes.length === checkboxes.length) {
            selectAllBtn.textContent = 'Deselect All';
        } else {
            selectAllBtn.textContent = 'Select All';
        }
    }

    toggleSelectAll() {
        const checkboxes = document.querySelectorAll('.line_checkbox');
        const allSelected = Array.from(checkboxes).every(cb => cb.checked);

        checkboxes.forEach(checkbox => {
            checkbox.checked = !allSelected;
            checkbox.dispatchEvent(new Event('change', { bubbles: true }));
        });
    }

    async refreshData() {
        this.state.isLoading = true;
        await this.loadReconcileData();
        this.state.isLoading = false;
        this.showNotification("Data refreshed successfully", 'success');
    }

    async performReconciliation() {
        if (this.state.selectedLines.size === 0) {
            this.showNotification("Please select at least one line to reconcile", 'warning');
            return;
        }

        if (Math.abs(this.state.summary.difference) > 0.01) {
            this.showNotification("Reconciliation is not balanced. Please check your selection.", 'warning');
            return;
        }

        this.state.isReconciling = true;
        this.updateReconcileButtonState();

        try {
            const paymentId = this.getPaymentId();
            const selectedLineIds = Array.from(this.state.selectedLines);

            const response = await fetch('/payment_reconcile/reconcile', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        payment_id: paymentId,
                        selected_line_ids: selectedLineIds
                    },
                    id: new Date().getTime()
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();

            if (result.error) {
                throw new Error(result.error);
            }

            this.showNotification("Reconciliation completed successfully!", 'success');

            setTimeout(() => {
                this.refreshData();
            }, 1500);

        } catch (error) {
            console.error("Reconciliation error:", error);
            this.showNotification(`Reconciliation failed: ${error.message}`, 'error');
        } finally {
            this.state.isReconciling = false;
            this.updateReconcileButtonState();
        }
    }

    showNotification(message, type = 'info') {
        console.log(`[${type.toUpperCase()}] ${message}`);

        if (typeof odoo !== 'undefined' && odoo.services && odoo.services.notification) {
            odoo.services.notification.add(message, { type });
            return;
        }

        const alertClass = {
            'success': 'alert-success',
            'error': 'alert-danger',
            'warning': 'alert-warning',
            'info': 'alert-info'
        }[type] || 'alert-info';

        const notification = document.createElement('div');
        notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            <strong>${type.charAt(0).toUpperCase() + type.slice(1)}:</strong> ${message}
            <button type="button" class="close" aria-label="Close">
                <span aria-hidden="true">&times;</span>
            </button>
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);

        const closeBtn = notification.querySelector('.close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            });
        }
    }
}

// ENHANCED INITIALIZATION WITH ODOO MANY2ONE AWARENESS
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing enhanced Many2one-aware detection...');

    function enhancedInitialization() {
        console.log('Starting enhanced initialization...');

        // Method 1: Direct container check
        const directContainer = document.querySelector('.payment_reconcile_widget');
        if (directContainer) {
            console.log('✓ Direct container found immediately');
            startController();
            return true;
        }

        // Method 2: Wait for Odoo form view with Many2one fields
        const formView = document.querySelector('.o_form_view');
        if (formView) {
            console.log('✓ Form view detected, checking for Many2one widgets...');
            setupMany2oneObserver();
            return true;
        }

        // Method 3: Check if we're in the right context
        const isReconcileWidget = window.location.href.includes('payment.reconcile.widget') ||
                                document.querySelector('.o_payment_reconcile_form') ||
                                document.title.includes('Payment Reconciliation');

        if (isReconcileWidget) {
            console.log('✓ Reconcile widget context detected, setting up polling...');
            setupPollingMethod();
            return true;
        }

        console.log('✗ No container or context detected');
        return false;
    }

    function startController() {
        console.log('Starting PaymentReconcileController...');
        const controller = new PaymentReconcileController();
        controller.start().catch(error => {
            console.error('Failed to start PaymentReconcileController:', error);
        });
    }

    function setupMany2oneObserver() {
        console.log('Setting up Many2one-aware MutationObserver...');

        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                if (mutation.type === 'childList') {
                    for (const node of mutation.addedNodes) {
                        if (node.nodeType === Node.ELEMENT_NODE) {
                            // Check for widget container
                            const widget = node.querySelector ?
                                node.querySelector('.payment_reconcile_widget') : null;

                            if (widget || node.classList?.contains('payment_reconcile_widget')) {
                                console.log('✓ Payment widget detected via MutationObserver');
                                observer.disconnect();
                                startController();
                                return;
                            }

                            // Check for Many2one payment fields being added
                            const paymentField = node.querySelector ?
                                node.querySelector('.o_field_many2one[name="payment_id"], [data-field-name="payment_id"]') : null;

                            if (paymentField || (node.getAttribute && node.getAttribute('data-field-name') === 'payment_id')) {
                                console.log('✓ Payment Many2one field detected, checking for widget...');
                                // Give a moment for the widget container to be added
                                setTimeout(() => {
                                    const container = document.querySelector('.payment_reconcile_widget');
                                    if (container) {
                                        console.log('✓ Widget container found after Many2one detection');
                                        observer.disconnect();
                                        startController();
                                    }
                                }, 500);
                            }
                        }
                    }
                }
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });

        setTimeout(() => {
            observer.disconnect();
            console.log('Many2one MutationObserver timeout - disconnected');
        }, 30000);
    }

    function setupPollingMethod() {
        console.log('Setting up polling method for container detection...');

        let attempts = 0;
        const maxAttempts = 100;
        const pollInterval = 200;

        const pollForContainer = () => {
            attempts++;

            const selectors = [
                '.payment_reconcile_widget',
                '#payment_reconcile_main_container',
                '.payment_reconcile_widget_container .payment_reconcile_widget',
                '.o_form_sheet .payment_reconcile_widget'
            ];

            for (const selector of selectors) {
                const container = document.querySelector(selector);
                if (container) {
                    console.log(`✓ Container found via polling (${selector}) after ${attempts} attempts`);
                    startController();
                    return;
                }
            }

            if (attempts < maxAttempts) {
                setTimeout(pollForContainer, pollInterval);
            } else {
                console.log(`✗ Container not found after ${maxAttempts} polling attempts`);
            }
        };

        pollForContainer();
    }

    // Start the enhanced initialization
    if (!enhancedInitialization()) {
        console.log('Initial detection failed, retrying after delay...');
        setTimeout(() => {
            if (!enhancedInitialization()) {
                console.log('Second attempt failed, trying polling as last resort...');
                setupPollingMethod();
            }
        }, 2000);
    }
});

// Export for global access and debugging
if (typeof window !== 'undefined') {
    window.PaymentReconcileController = PaymentReconcileController;

    // Enhanced debugging helper for Many2one fields
    window.debugPaymentWidget = function() {
        console.log('=== ENHANCED PAYMENT WIDGET DEBUG (Many2one Focus) ===');

        console.log('1. Container Detection:');
        const containerSelectors = [
            '.payment_reconcile_widget',
            '#payment_reconcile_main_container',
            '.payment_reconcile_widget_container'
        ];

        containerSelectors.forEach(selector => {
            const element = document.querySelector(selector);
            console.log(`${selector}: ${element ? 'FOUND' : 'NOT FOUND'}`);
        });

        console.log('2. Many2one Widget Analysis:');
        const many2oneWidgets = document.querySelectorAll('.o_field_many2one, [data-field-name="payment_id"]');
        console.log(`Total Many2one widgets: ${many2oneWidgets.length}`);

        many2oneWidgets.forEach((widget, i) => {
            const fieldName = widget.getAttribute('name') || widget.getAttribute('data-field-name');
            console.log(`Widget ${i}: field="${fieldName}"`);

            if (fieldName === 'payment_id' || widget.getAttribute('name') === 'payment_id') {
                console.log(`  PAYMENT WIDGET FOUND!`);

                // Check data attributes
                const dataAttrs = ['data-value', 'data-id', 'data-selected-id'];
                dataAttrs.forEach(attr => {
                    const value = widget.getAttribute(attr);
                    console.log(`    ${attr}: ${value || 'none'}`);
                });

                // Check hidden inputs
                const hiddenInputs = widget.querySelectorAll('input[type="hidden"]');
                console.log(`    Hidden inputs: ${hiddenInputs.length}`);
                hiddenInputs.forEach((input, j) => {
                    console.log(`      ${j}: name="${input.name}" value="${input.value}"`);
                });

                // Check selects
                const selects = widget.querySelectorAll('select');
                console.log(`    Select elements: ${selects.length}`);
                selects.forEach((select, j) => {
                    console.log(`      ${j}: value="${select.value}" options=${select.options.length}`);
                    if (select.selectedIndex >= 0) {
                        const option = select.options[select.selectedIndex];
                        console.log(`        selected: "${option.value}" - "${option.text}"`);
                    }
                });
            }
        });

        console.log('3. Standard Form Fields:');
        const standardFields = document.querySelectorAll('input[name="payment_id"], select[name="payment_id"]');
        console.log(`Standard payment fields: ${standardFields.length}`);
        standardFields.forEach((field, i) => {
            console.log(`  ${i}: ${field.tagName} value="${field.value}"`);
        });

        console.log('4. All Payment-related Elements:');
        const allPaymentElements = document.querySelectorAll('[name*="payment"], [data-field-name*="payment"], [class*="payment"]');
        console.log(`Total payment elements: ${allPaymentElements.length}`);

        console.log('5. Test Payment ID Extraction:');
        const controller = new PaymentReconcileController();
        const extractedId = controller.extractPaymentIdFromForm();
        console.log(`Extracted payment ID: ${extractedId}`);

        console.log('=== END ENHANCED DEBUG ===');
    };

    // Helper function to manually trigger payment ID extraction
    window.extractPaymentId = function() {
        const controller = new PaymentReconcileController();
        const paymentId = controller.extractPaymentIdFromForm();
        console.log('Manual payment ID extraction result:', paymentId);
        return paymentId;
    };
}

console.log('Enhanced Payment Reconcile Widget JavaScript (Many2one-aware) loaded successfully');