// This is a temporary file to fix the socket initialization issue

// Function to set up wallet update listener
function setupWalletUpdateListener() {
    if (typeof socket === 'undefined' || socket === null) {
        console.log('Socket not available, retrying in 1 second...');
        setTimeout(setupWalletUpdateListener, 1000);
        return;
    }
    
    console.log('Setting up wallet_updated listener');
    socket.on('wallet_updated', function(data) {
        try {
            if (data && data.user_id && window.userId && data.user_id === parseInt(window.userId, 10)) {
                // Update wallet balance display with animation
                const balanceElements = document.querySelectorAll('.wallet-balance, .badge.bg-success, .wallet-balance-display');
                balanceElements.forEach(el => {
                    const currentBalance = parseFloat(el.textContent.replace(/[^0-9.-]+/g, '')) || 0;
                    animateBalance(el, currentBalance, data.new_balance);
                });
                
                // Show toast notification
                const toastEl = document.createElement('div');
                toastEl.className = 'toast align-items-center text-white bg-success border-0';
                toastEl.setAttribute('role', 'alert');
                toastEl.setAttribute('aria-live', 'assertive');
                toastEl.setAttribute('aria-atomic', 'true');
                
                const isDebit = data.amount < 0;
                const amount = Math.abs(parseFloat(data.amount) || 0);
                
                toastEl.innerHTML = `
                    <div class="d-flex">
                        <div class="toast-body">
                            <i class="fas ${isDebit ? 'fa-arrow-down' : 'fa-arrow-up'} me-2"></i>
                            ${isDebit ? 'Deducted' : 'Added'} ₹${amount.toFixed(2)}
                            ${data.description ? 'for ' + data.description : ''}
                        </div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                    </div>`;
                
                const toastContainer = document.getElementById('toastContainer');
                if (toastContainer) {
                    toastContainer.appendChild(toastEl);
                    const toast = new bootstrap.Toast(toastEl);
                    toast.show();
                    
                    // Remove toast after it's hidden
                    toastEl.addEventListener('hidden.bs.toast', function() {
                        toastEl.remove();
                    });
                }
                
                // Refresh transactions if on wallet page
                if (window.location.pathname === '/wallet' && typeof refreshTransactions === 'function') {
                    refreshTransactions();
                }
            }
        } catch (error) {
            console.error('Error in wallet_updated handler:', error);
        }
    });
}

// Call the function to set up the listener
setupWalletUpdateListener();
