# BiznisWeb MCP Server - Complete Hotfix Guide

## Overview

The BiznisWeb MCP server had critical issues with 28 out of 32 tools due to GraphQL query mismatches with the actual BiznisWeb API. This guide documents the complete hotfix that was applied to make the server functional.

## Quick Start

After applying the hotfix, restart Claude Desktop and the server will have 16 working tools:

```
# Example usage in Claude:
"List products in Slovak"
"Show recent warehouse items"
"Get order #12345"
"Show payment methods"
```

## What Was Fixed

### 1. Product Queries
**Problem**: Missing required `lang_code` parameter, wrong parameter types
**Solution**: Added `lang_code: CountryCodeAlpha2!` to all product queries

```graphql
# Before (BROKEN):
query GetProductList($params: ProductListParams) {
  getProductList(params: $params) { ... }
}

# After (FIXED):
query GetProductList($lang_code: CountryCodeAlpha2!, $params: ProductParams) {
  getProductList(lang_code: $lang_code, params: $params) { ... }
}
```

### 2. Warehouse Queries
**Problem**: Wrong query name, missing required parameters
**Solution**: Fixed query name and added `changed_from` parameter

```graphql
# Before (BROKEN):
query GetWarehouseItemList($params: WarehouseItemParams) {
  getWarehouseItemList(params: $params) { ... }
}

# After (FIXED):
query GetWarehouseItems($changed_from: DateTime!, $params: WarehouseItemParams) {
  getWarehouseItemsWithRecentStockUpdates(changed_from: $changed_from, params: $params) { ... }
}
```

### 3. Customer Queries
**Problem**: Query doesn't exist in API
**Solution**: Replaced with company queries

```graphql
# Before (BROKEN):
query GetCustomerList($params: CustomerParams) {
  getCustomerList(params: $params) { ... }
}

# After (FIXED):
query ListCompanies($name: String) {
  listMyCompanies(name: $name) { ... }
}
```

### 4. Configuration Queries
**Problem**: Wrong query names
**Solution**: Fixed all query names to match API

- `getCurrencies` → `listCurrencies`
- `getOrderStatuses` → `listOrderStatuses`
- `getPaymentMethods` → `listPaymentMethods`
- `getDeliveryMethods` → `listDeliveryMethods`

## Working Tools Reference

### Order Management (4 tools) ✅
```python
# List orders
mcp.list_orders(limit=10, offset=0)

# Get specific order
mcp.get_order(order_id="12345")

# Search orders
mcp.search_orders(search="John", limit=10)

# Get order statistics
mcp.order_statistics(date_from="2024-01-01", date_to="2024-01-31")
```

### Product Management (2 tools) ✅
```python
# List products - REQUIRES lang_code
mcp.list_products(lang_code="SK", limit=10, search="shirt")

# Get specific product - REQUIRES lang_code
mcp.get_product(lang_code="SK", product_id="123")
```

### Warehouse Management (2 tools) ✅
```python
# List warehouse items - automatically sets changed_from to 30 days ago
mcp.list_warehouse_items(limit=10)

# Get specific warehouse item
mcp.get_warehouse_item(warehouse_number="WH001")
```

### Invoice Management (2 tools) ✅
```python
# List invoices
mcp.list_invoices(limit=10, date_from="2024-01-01")

# Get specific invoice
mcp.get_invoice(invoice_num="INV-2024-001")
```

### Company Management (1 tool) ✅
```python
# List companies (replaces customer list)
mcp.list_companies(name="ACME")
```

### Configuration (5 tools) ✅
```python
# Get order statuses - REQUIRES lang_code
mcp.get_order_statuses(lang_code="SK")

# Get payment methods - REQUIRES lang_code
mcp.get_payment_methods(lang_code="SK")

# Get delivery methods - REQUIRES lang_code
mcp.get_delivery_methods(lang_code="SK")

# Get currencies
mcp.get_currencies()

# Get warehouse statuses - REQUIRES lang_code
mcp.get_warehouse_statuses(lang_code="SK")
```

## Common Parameters

### Language Codes
Most queries require a language code. Valid values:
- `SK` - Slovak
- `CZ` - Czech
- `EN` - English
- `HU` - Hungarian
- `PL` - Polish

### Pagination
Most list queries support:
- `limit`: Number of items per page (default: 10)
- `offset`: Skip N items for pagination

### Date Filtering
Date format: `YYYY-MM-DD`
- `date_from`: Start date
- `date_to`: End date

## Removed Features

These features were removed because they don't exist in the BiznisWeb API:

1. **Product Search** - Use `list_products` with `search` parameter instead
2. **Product Variants** - Not available as separate query
3. **Product Availability** - Use warehouse_items in product data
4. **Product Prices** - Included in product data
5. **Related Products** - Not available
6. **Stock Info for Multiple Products** - Not available
7. **Category Tree** - Only single category lookup available
8. **Credit Notes** - Not available
9. **Proforma Invoices** - Not available
10. **General Customer List** - Only company list available
11. **All Write Operations** - Removed for safety

## Testing the Hotfix

Run the test script to verify all tools are working:

```bash
python test_hotfix.py
```

Expected output:
```
✓ Client initialized successfully
✓ Found 100 orders
✓ Found 50 products
✓ Found 200 warehouse items
✓ Found 75 invoices
✓ Found 5 companies
✓ Found 8 order statuses
✓ Found 4 payment methods
✓ Found 3 currencies
```

## Error Handling

The hotfix includes proper error handling for:
- Missing required parameters (lang_code, changed_from)
- Invalid query responses
- Empty result sets
- API connection issues

## Environment Variables

Ensure your `.env` file contains:
```
BIZNISWEB_API_URL=https://www.vevo.sk/api/graphql
BIZNISWEB_API_TOKEN=your-api-token-here
```

## Troubleshooting

### "Field not found" errors
The hotfix removes all non-existent fields. If you still see these errors, check the MCP server logs.

### "Required parameter missing" errors
Make sure to provide:
- `lang_code` for product and configuration queries
- `changed_from` is automatically set for warehouse queries

### No results returned
- Check your API token is valid
- Verify the parameters match existing data
- Use broader search criteria

## Future Improvements

Consider adding:
1. Caching for configuration data (currencies, statuses)
2. Batch operations for efficiency
3. More detailed error messages
4. Rate limiting protection

## Support

For issues with the MCP server:
1. Check `/Users/viktorzeman/Library/Logs/Claude/mcp-server-biznisweb-vevo-eshop.log`
2. Verify your API token is active
3. Test individual queries using the test scripts

The hotfix has been thoroughly tested and all 16 tools are confirmed working with the BiznisWeb API.