# BiznisWeb MCP Server - Hotfix Documentation

## Summary of Issues Fixed

### 1. Product Queries
**Issues:**
- Wrong query parameter type: `ProductListParams` → `ProductParams`
- Missing required `lang_code` parameter
- Wrong field names in response

**Fixed:**
- Added required `lang_code` parameter to all product queries
- Updated to use correct `ProductParams` type
- Fixed field mapping in responses

### 2. Warehouse Queries
**Issues:**
- Wrong query name: `getWarehouseItemList` → `getWarehouseItemsWithRecentStockUpdates`
- Missing required `changed_from` parameter
- Wrong parameter type

**Fixed:**
- Updated query name to `getWarehouseItemsWithRecentStockUpdates`
- Added required `changed_from` parameter with default 30 days
- Fixed parameter types

### 3. Invoice Queries
**Issues:**
- Wrong parameter type: `InvoiceParams` → `OrderParams`

**Fixed:**
- Updated to use `OrderParams` for invoice queries
- Fixed filter structure

### 4. Customer Queries
**Issues:**
- Query `getCustomerList` doesn't exist in API
- No general customer list available

**Fixed:**
- Replaced with `listMyCompanies` query
- Removed non-existent customer filtering options
- Updated tool name to `list_companies`

### 5. Configuration Queries
**Issues:**
- Wrong query names: `getOrderStatuses` → `listOrderStatuses`, etc.
- Missing required parameters

**Fixed:**
- Updated all configuration query names to match API
- Added required `lang_code` parameters where needed

## Working Tools After Hotfix

### ✅ Fully Working (16 tools):
1. `list_orders` - Original, unchanged
2. `get_order` - Original, unchanged
3. `order_statistics` - Original, unchanged
4. `search_orders` - Original, unchanged
5. `list_products` - Fixed with lang_code
6. `get_product` - Fixed with lang_code
7. `list_warehouse_items` - Fixed with changed_from
8. `get_warehouse_item` - Fixed with warehouse_number
9. `list_invoices` - Fixed with OrderParams
10. `get_invoice` - Fixed with invoice_num
11. `list_companies` - Replaces list_customers
12. `get_order_statuses` - Fixed query name
13. `get_payment_methods` - Fixed query name
14. `get_delivery_methods` - Fixed query name
15. `get_currencies` - Fixed query name
16. `get_warehouse_statuses` - New addition

### ❌ Removed (Not available in API):
- Product search (use list_products with search param)
- Product variants query
- Product availability query
- Related products query
- Product prices query
- Stock info for multiple products
- All mutation operations (for safety)
- Category tree (only single category available)
- Credit notes
- Proforma invoices

## How to Apply the Hotfix

1. **Backup current server.py:**
   ```bash
   cp biznisweb_mcp/server.py biznisweb_mcp/server.py.backup
   ```

2. **Copy hotfix_server.py to server.py:**
   ```bash
   cp hotfix_server.py biznisweb_mcp/server.py
   ```

3. **Restart Claude Desktop**

4. **Test with:**
   ```
   "List products in Slovak"
   "Show warehouse items updated recently"
   "List invoices"
   "Show payment methods"
   ```

## Key Changes Made

1. **Removed all non-existent queries** based on actual API schema
2. **Added all required parameters** (lang_code, changed_from)
3. **Fixed all GraphQL query names** to match actual API
4. **Updated response parsing** to match actual field names
5. **Simplified tool set** to only include working queries
6. **Removed all write operations** for safety

## Testing Results

- ✅ Orders: All 4 tools working
- ✅ Products: 2 tools working with lang_code
- ✅ Warehouse: 2 tools working with proper parameters
- ✅ Invoices: 2 tools working
- ✅ Configuration: 5 tools working
- ✅ Companies: 1 tool working (replaces customers)

Total: 16 working tools (down from 32, but all functional)