from flask_login import login_required
from flask import redirect, url_for, flash

from . import expenses_bp


@expenses_bp.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    """DEPRECATED: Expenses have been merged into the Payments Hub.
    
    All outgoing disbursements (supplier payments, staff salaries, 
    operational costs) are now recorded through the Payments tab 
    with proper financial statement category and line item classification.
    """
    flash('Expenses have been consolidated into the Payments Hub. Please use Payments to record all outgoing disbursements.', 'info')
    return redirect(url_for('purchases.payments'))

