from app import create_app
from models import db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    columns = inspector.get_columns('sales')
    print('Columns in sales table:')
    for col in columns:
        col_name = col['name']
        col_type = col['type']
        print(f'  - {col_name}: {col_type}')
    
    # Check if invoice_id column exists
    col_names = [col['name'] for col in columns]
    if 'invoice_id' in col_names:
        print('\n✓ SUCCESS: invoice_id column was added to sales table')
    else:
        print('\n✗ ERROR: invoice_id column was NOT added to sales table')
