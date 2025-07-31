#!/usr/bin/env python3
"""
BiznisWeb MCP Server - HOTFIX VERSION
Fixed all GraphQL queries to match actual API schema
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server
from dotenv import load_dotenv
from gql import gql, Client
from gql.transport.httpx import HTTPXAsyncTransport

# Load environment variables
load_dotenv()

# Configuration
API_URL = os.getenv('BIZNISWEB_API_URL', 'https://www.vevo.sk/api/graphql')
API_TOKEN = os.getenv('BIZNISWEB_API_TOKEN')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================
# CORRECTED GRAPHQL QUERIES BASED ON ACTUAL API
# ============================================

# Original working queries (unchanged)
ORDER_LIST_QUERY = gql("""
query GetOrders($status: Int, $newer_from: DateTime, $changed_from: DateTime, $params: OrderParams, $filter: OrderFilter) {
  getOrderList(status: $status, newer_from: $newer_from, changed_from: $changed_from, params: $params, filter: $filter) {
    data {
      id
      order_num
      pur_date
      status {
        id
        name
      }
      customer {
        ... on Company {
          company_name
          email
        }
        ... on Person {
          name
          surname
          email
        }
        ... on UnauthenticatedEmail {
          email
        }
      }
      sum {
        value
        currency {
          code
        }
      }
      items {
        item_label
        quantity
        price {
          value
        }
      }
    }
    pageInfo {
      hasNextPage
      nextCursor
      totalPages
    }
  }
}
""")

ORDER_DETAIL_QUERY = gql("""
query GetOrder($orderNum: String!) {
  getOrder(order_num: $orderNum) {
    id
    order_num
    external_ref
    pur_date
    var_symb
    last_change
    status {
      id
      name
    }
    customer {
      ... on Company {
        company_name
        company_id
        vat_id
        email
        phone
      }
      ... on Person {
        name
        surname
        email
        phone
      }
    }
    invoice_address {
      street
      city
      zip
      country
    }
    delivery_address {
      street
      city
      zip
      country
    }
    items {
      item_label
      ean
      quantity
      tax_rate
      price {
        value
        formatted
      }
    }
    sum {
      value
      formatted
      currency {
        code
        symbol
      }
    }
  }
}
""")

# FIXED: Product queries with correct parameters
PRODUCT_LIST_QUERY = gql("""
query GetProductList($lang_code: CountryCodeAlpha2!, $params: ProductParams, $filter: ProductFilter) {
  getProductList(lang_code: $lang_code, params: $params, filter: $filter) {
    data {
      id
      title
      link
      short
      ean
      main_category {
        id
        title
      }
      warehouse_items {
        id
        warehouse_number
        quantity
        status {
          id
          name
        }
      }
    }
    pageInfo {
      hasNextPage
      nextCursor
    }
  }
}
""")

PRODUCT_DETAIL_QUERY = gql("""
query GetProduct($product_id: ID!, $lang_code: CountryCodeAlpha2!) {
  getProduct(product_id: $product_id, lang_code: $lang_code) {
    id
    title
    link
    short
    ean
    main_category {
      id
      title
    }
    attribute_category {
      id
      title
    }
    attributes {
      id
      title
      values
    }
    assigned_categories {
      id
      title
    }
    warehouse_items {
      id
      warehouse_number
      ean
      quantity
      status {
        id
        name
      }
    }
  }
}
""")

# FIXED: Warehouse queries
WAREHOUSE_ITEMS_QUERY = gql("""
query GetWarehouseItems($changed_from: DateTime!, $params: WarehouseItemParams) {
  getWarehouseItemsWithRecentStockUpdates(changed_from: $changed_from, params: $params) {
    data {
      id
      ean
      warehouse_number
      quantity
      status {
        id
        name
      }
      weight {
        value
        unit
      }
    }
    pageInfo {
      hasNextPage
      nextCursor
    }
  }
}
""")

WAREHOUSE_ITEM_DETAIL_QUERY = gql("""
query GetWarehouseItem($warehouse_number: WarehouseNumber!) {
  getWarehouseItem(warehouse_number: $warehouse_number) {
    id
    warehouse_number
    ean
    quantity
    status {
      id
      name
    }
    weight {
      value
      unit
    }
  }
}
""")

# FIXED: Invoice queries
INVOICE_LIST_QUERY = gql("""
query GetInvoiceList($params: OrderParams, $filter: InvoiceFilter) {
  getInvoiceList(params: $params, filter: $filter) {
    data {
      id
      invoice_num
      order {
        order_num
      }
      customer {
        ... on Company {
          company_name
          company_id
        }
        ... on Person {
          name
          surname
        }
      }
      invoice_address {
        street
        city
        zip
        country
      }
      sum {
        value
        currency {
          code
        }
      }
    }
    pageInfo {
      hasNextPage
      nextCursor
    }
  }
}
""")

INVOICE_DETAIL_QUERY = gql("""
query GetInvoice($invoice_num: String!) {
  getInvoice(invoice_num: $invoice_num) {
    id
    invoice_num
    order {
      order_num
    }
    supplier {
      company_name
    }
    customer {
      ... on Company {
        company_name
        company_id
        vat_id
      }
      ... on Person {
        name
        surname
        email
      }
    }
    invoice_address {
      street
      city
      zip
      country
    }
    items {
      item_label
      warehouse_number
      ean
      quantity
      price {
        value
        currency {
          code
        }
      }
    }
    sum {
      value
      currency {
        code
      }
    }
  }
}
""")

# FIXED: Company query (no customer list exists)
COMPANIES_LIST_QUERY = gql("""
query ListCompanies($name: String) {
  listMyCompanies(name: $name) {
    id
    company_name
    company_id
    vat_id
  }
}
""")

# FIXED: Category query
CATEGORY_QUERY = gql("""
query GetCategory($category_id: ID!) {
  getCategory(category_id: $category_id) {
    id
    title
    parent_category {
      id
      title
    }
    children_categories {
      id
      title
    }
  }
}
""")

# FIXED: Configuration queries
ORDER_STATUSES_QUERY = gql("""
query ListOrderStatuses($lang_code: CountryCodeAlpha2!) {
  listOrderStatuses(lang_code: $lang_code) {
    id
    name
    color
  }
}
""")

PAYMENT_METHODS_QUERY = gql("""
query ListPayments($lang_code: CountryCodeAlpha2!) {
  listPayments(lang_code: $lang_code) {
    id
    name
    price {
      value
      currency {
        code
      }
    }
  }
}
""")

DELIVERY_METHODS_QUERY = gql("""
query ListShippings($lang_code: CountryCodeAlpha2!) {
  listShippings(lang_code: $lang_code) {
    id
    name
    price {
      value
      currency {
        code
      }
    }
  }
}
""")

CURRENCIES_QUERY = gql("""
query ListCurrencies {
  listCurrencies {
    id
    code
    symbol
    name
  }
}
""")

WAREHOUSE_STATUSES_QUERY = gql("""
query ListWarehouseStatuses($lang_code: CountryCodeAlpha2) {
  listWarehouseStatuses(lang_code: $lang_code) {
    id
    name
    allow_order
  }
}
""")


class BiznisWebMCPServer:
    def __init__(self):
        self.server = Server("biznisweb-mcp")
        self.client = None
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Set up MCP server handlers"""
        
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools"""
            return [
                # Original working tools
                Tool(
                    name="list_orders",
                    description="List orders with optional date filtering",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "from_date": {
                                "type": "string",
                                "description": "From date in YYYY-MM-DD format"
                            },
                            "to_date": {
                                "type": "string",
                                "description": "To date in YYYY-MM-DD format"
                            },
                            "status": {
                                "type": "integer",
                                "description": "Order status ID"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of orders to return",
                                "default": 30
                            }
                        }
                    }
                ),
                Tool(
                    name="get_order",
                    description="Get detailed information about a specific order",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "order_num": {
                                "type": "string",
                                "description": "Order number"
                            }
                        },
                        "required": ["order_num"]
                    }
                ),
                Tool(
                    name="order_statistics",
                    description="Get order statistics for a date range",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "from_date": {
                                "type": "string",
                                "description": "From date in YYYY-MM-DD format"
                            },
                            "to_date": {
                                "type": "string",
                                "description": "To date in YYYY-MM-DD format"
                            }
                        }
                    }
                ),
                Tool(
                    name="search_orders",
                    description="Search orders by customer or order number",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query (customer name or order number)"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                
                # Fixed Product tools
                Tool(
                    name="list_products",
                    description="List products (requires language code)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "lang_code": {
                                "type": "string",
                                "description": "Language code (SK, EN, etc.)",
                                "default": "SK"
                            },
                            "category_id": {
                                "type": "integer",
                                "description": "Filter by category ID"
                            },
                            "active": {
                                "type": "boolean",
                                "description": "Show only active products"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of products (max 30)",
                                "default": 30
                            },
                            "search": {
                                "type": "string",
                                "description": "Search in product names"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_product",
                    description="Get detailed product information",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "string",
                                "description": "Product ID"
                            },
                            "lang_code": {
                                "type": "string",
                                "description": "Language code (SK, EN, etc.)",
                                "default": "SK"
                            }
                        },
                        "required": ["product_id"]
                    }
                ),
                
                # Fixed Warehouse tools
                Tool(
                    name="list_warehouse_items",
                    description="List warehouse items with recent updates",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "changed_from": {
                                "type": "string",
                                "description": "Show items changed from date (YYYY-MM-DD)",
                                "default": "30 days ago"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of items (max 30)",
                                "default": 30
                            }
                        }
                    }
                ),
                Tool(
                    name="get_warehouse_item",
                    description="Get warehouse item by warehouse number",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "warehouse_number": {
                                "type": "string",
                                "description": "Warehouse number"
                            }
                        },
                        "required": ["warehouse_number"]
                    }
                ),
                
                # Fixed Invoice tools
                Tool(
                    name="list_invoices",
                    description="List invoices with optional filtering",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "buy_date_from": {
                                "type": "string",
                                "description": "From purchase date (YYYY-MM-DD)"
                            },
                            "buy_date_to": {
                                "type": "string",
                                "description": "To purchase date (YYYY-MM-DD)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of invoices (max 30)",
                                "default": 30
                            }
                        }
                    }
                ),
                Tool(
                    name="get_invoice",
                    description="Get invoice details",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "invoice_num": {
                                "type": "string",
                                "description": "Invoice number"
                            }
                        },
                        "required": ["invoice_num"]
                    }
                ),
                
                # Fixed Company tools (no customer list)
                Tool(
                    name="list_companies",
                    description="List your companies",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Search by company name"
                            }
                        }
                    }
                ),
                
                # Fixed Configuration tools
                Tool(
                    name="get_order_statuses",
                    description="Get list of order statuses",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "lang_code": {
                                "type": "string",
                                "description": "Language code (SK, EN, etc.)",
                                "default": "SK"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_payment_methods",
                    description="Get available payment methods",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "lang_code": {
                                "type": "string",
                                "description": "Language code (SK, EN, etc.)",
                                "default": "SK"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_delivery_methods",
                    description="Get available delivery methods",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "lang_code": {
                                "type": "string",
                                "description": "Language code (SK, EN, etc.)",
                                "default": "SK"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_currencies",
                    description="Get list of currencies",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="get_warehouse_statuses",
                    description="Get warehouse statuses",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "lang_code": {
                                "type": "string",
                                "description": "Language code (SK, EN, etc.)",
                                "default": "SK"
                            }
                        }
                    }
                ),
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            try:
                if not self.client:
                    await self._init_client()
                
                # Route to appropriate handler
                if name == "list_orders":
                    result = await self._list_orders(arguments)
                elif name == "get_order":
                    result = await self._get_order(arguments)
                elif name == "order_statistics":
                    result = await self._order_statistics(arguments)
                elif name == "search_orders":
                    result = await self._search_orders(arguments)
                elif name == "list_products":
                    result = await self._list_products(arguments)
                elif name == "get_product":
                    result = await self._get_product(arguments)
                elif name == "list_warehouse_items":
                    result = await self._list_warehouse_items(arguments)
                elif name == "get_warehouse_item":
                    result = await self._get_warehouse_item(arguments)
                elif name == "list_invoices":
                    result = await self._list_invoices(arguments)
                elif name == "get_invoice":
                    result = await self._get_invoice(arguments)
                elif name == "list_companies":
                    result = await self._list_companies(arguments)
                elif name == "get_order_statuses":
                    result = await self._get_order_statuses(arguments)
                elif name == "get_payment_methods":
                    result = await self._get_payment_methods(arguments)
                elif name == "get_delivery_methods":
                    result = await self._get_delivery_methods(arguments)
                elif name == "get_currencies":
                    result = await self._get_currencies(arguments)
                elif name == "get_warehouse_statuses":
                    result = await self._get_warehouse_statuses(arguments)
                else:
                    result = {"error": f"Unknown tool: {name}"}
                
                return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
                
            except Exception as e:
                logger.error(f"Error in tool {name}: {str(e)}")
                result = {"error": str(e)}
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    async def _init_client(self):
        """Initialize GraphQL client"""
        if not API_TOKEN:
            raise ValueError("BIZNISWEB_API_TOKEN not found in environment variables")
        
        transport = HTTPXAsyncTransport(
            url=API_URL,
            headers={
                'BW-API-Key': f'Token {API_TOKEN}',
                'Content-Type': 'application/json'
            }
        )
        self.client = Client(transport=transport, fetch_schema_from_transport=False)
    
    # Original working methods (keep as-is)
    async def _list_orders(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List orders with optional filtering"""
        variables = {}
        
        if 'from_date' in args:
            variables['newer_from'] = args['from_date'] + 'T00:00:00'
        
        if 'status' in args:
            variables['status'] = args['status']
        
        variables['params'] = {
            'limit': min(args.get('limit', 30), 30),  # Max 30
            'order_by': 'pur_date',
            'sort': 'DESC'
        }
        
        async with self.client as session:
            result = await session.execute(ORDER_LIST_QUERY, variable_values=variables)
        
        orders_data = result.get('getOrderList', {})
        orders = orders_data.get('data', [])
        page_info = orders_data.get('pageInfo', {})
        
        # Format orders for better readability
        formatted_orders = []
        for order in orders:
            try:
                customer = order.get('customer', {})
                customer_name = customer.get('company_name', '')
                if not customer_name:
                    customer_name = f"{customer.get('name', '')} {customer.get('surname', '')}".strip()
                
                order_sum = order.get('sum', {})
                order_value = order_sum.get('value', 'N/A')
                currency_code = order_sum.get('currency', {}).get('code', '')
                
                formatted_orders.append({
                    'order_num': order['order_num'],
                    'date': order['pur_date'],
                    'customer': customer_name,
                    'email': customer.get('email'),
                    'status': order.get('status', {}).get('name'),
                    'total': f"{order_value} {currency_code}".strip(),
                    'items_count': len(order.get('items', []))
                })
            except Exception as e:
                logger.error(f"Error formatting order {order.get('order_num', 'unknown')}: {e}")
                continue
        
        return {
            'orders': formatted_orders,
            'count': len(formatted_orders),
            'has_more': page_info.get('hasNextPage', False),
            'total_pages': page_info.get('totalPages')
        }
    
    async def _get_order(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed order information"""
        order_num = args['order_num']
        
        async with self.client as session:
            result = await session.execute(ORDER_DETAIL_QUERY, variable_values={'orderNum': order_num})
        
        order = result.get('getOrder')
        if not order:
            return {'error': f'Order {order_num} not found'}
        
        # Format customer info
        customer = order.get('customer', {})
        customer_info = {
            'name': customer.get('company_name', '') or f"{customer.get('name', '')} {customer.get('surname', '')}".strip(),
            'email': customer.get('email'),
            'phone': customer.get('phone'),
            'company_id': customer.get('company_id'),
            'vat_id': customer.get('vat_id')
        }
        
        # Format addresses
        invoice_addr = order.get('invoice_address', {})
        delivery_addr = order.get('delivery_address', {})
        
        # Format items
        items = []
        for item in order.get('items', []):
            items.append({
                'name': item['item_label'],
                'ean': item.get('ean'),
                'quantity': item['quantity'],
                'price': item['price']['formatted'],
                'tax_rate': item.get('tax_rate')
            })
        
        return {
            'order_num': order['order_num'],
            'external_ref': order.get('external_ref'),
            'date': order['pur_date'],
            'last_change': order['last_change'],
            'status': order['status']['name'],
            'customer': customer_info,
            'invoice_address': {
                'street': invoice_addr.get('street'),
                'city': invoice_addr.get('city'),
                'zip': invoice_addr.get('zip'),
                'country': invoice_addr.get('country')
            },
            'delivery_address': {
                'street': delivery_addr.get('street'),
                'city': delivery_addr.get('city'),
                'zip': delivery_addr.get('zip'),
                'country': delivery_addr.get('country')
            } if delivery_addr else None,
            'items': items,
            'total': order['sum']['formatted']
        }
    
    async def _order_statistics(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get order statistics for date range"""
        # Keep existing implementation
        to_date = datetime.now()
        from_date = to_date - timedelta(days=30)
        
        if 'from_date' in args:
            from_date = datetime.strptime(args['from_date'], '%Y-%m-%d')
        if 'to_date' in args:
            to_date = datetime.strptime(args['to_date'], '%Y-%m-%d')
        
        # Simplified version - just count orders
        list_result = await self._list_orders({
            'from_date': from_date.strftime('%Y-%m-%d'),
            'to_date': to_date.strftime('%Y-%m-%d'),
            'limit': 30
        })
        
        return {
            'period': {
                'from': from_date.strftime('%Y-%m-%d'),
                'to': to_date.strftime('%Y-%m-%d')
            },
            'total_orders': list_result['count'],
            'has_more': list_result.get('has_more', False)
        }
    
    async def _search_orders(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search orders by customer or order number"""
        query = args['query'].lower()
        
        # Use order list with search
        variables = {
            'params': {
                'limit': 30,
                'order_by': 'pur_date',
                'sort': 'DESC',
                'search': args['query']  # API might support search param
            }
        }
        
        async with self.client as session:
            result = await session.execute(ORDER_LIST_QUERY, variable_values=variables)
        
        orders = result.get('getOrderList', {}).get('data', [])
        
        # Filter locally as backup
        matching_orders = []
        for order in orders:
            if query in order['order_num'].lower():
                matching_orders.append(order)
                continue
            
            customer = order.get('customer', {})
            customer_name = customer.get('company_name', '') or f"{customer.get('name', '')} {customer.get('surname', '')}".strip()
            customer_email = customer.get('email', '')
            
            if query in customer_name.lower() or query in customer_email.lower():
                matching_orders.append(order)
        
        # Format results
        formatted_results = []
        for order in matching_orders[:20]:
            customer = order.get('customer', {})
            customer_name = customer.get('company_name', '') or f"{customer.get('name', '')} {customer.get('surname', '')}".strip()
            
            formatted_results.append({
                'order_num': order['order_num'],
                'date': order['pur_date'],
                'customer': customer_name,
                'email': customer.get('email'),
                'status': order.get('status', {}).get('name'),
                'total': f"{order.get('sum', {}).get('value')} {order.get('sum', {}).get('currency', {}).get('code')}"
            })
        
        return {
            'query': args['query'],
            'results': formatted_results,
            'count': len(formatted_results)
        }
    
    # NEW FIXED METHODS
    
    async def _list_products(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List products with correct parameters"""
        try:
            lang_code = args.get('lang_code', 'SK')
            
            # Build params
            params = {
                'limit': min(args.get('limit', 30), 30),
            }
            
            if 'search' in args:
                params['search'] = args['search']
            
            # Build filter
            filter_dict = {}
            if 'category_id' in args:
                filter_dict['category'] = args['category_id']
            if 'active' in args:
                filter_dict['active'] = args['active']
            
            variables = {
                'lang_code': lang_code,
                'params': params
            }
            
            if filter_dict:
                variables['filter'] = filter_dict
            
            async with self.client as session:
                result = await session.execute(PRODUCT_LIST_QUERY, variable_values=variables)
            
            products_data = result.get('getProductList', {})
            products = products_data.get('data', [])
            page_info = products_data.get('pageInfo', {})
            
            # Format products
            formatted_products = []
            for product in products:
                # Calculate total stock
                total_stock = 0
                in_stock = False
                for item in product.get('warehouse_items', []):
                    quantity = item.get('quantity', 0)
                    total_stock += quantity
                    if quantity > 0:
                        in_stock = True
                
                formatted_products.append({
                    'id': product['id'],
                    'title': product.get('title', 'N/A'),
                    'link': product.get('link', ''),
                    'ean': product.get('ean', ''),
                    'category': product.get('main_category', {}).get('title', 'N/A'),
                    'in_stock': in_stock,
                    'total_stock': total_stock,
                    'short_description': product.get('short', '')
                })
            
            return {
                'products': formatted_products,
                'count': len(formatted_products),
                'has_more': page_info.get('hasNextPage', False),
                'language': lang_code
            }
            
        except Exception as e:
            logger.error(f"Error fetching products: {str(e)}")
            return {'error': f'Failed to fetch products: {str(e)}'}
    
    async def _get_product(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get product details"""
        try:
            product_id = args['product_id']
            lang_code = args.get('lang_code', 'SK')
            
            variables = {
                'product_id': product_id,
                'lang_code': lang_code
            }
            
            async with self.client as session:
                result = await session.execute(PRODUCT_DETAIL_QUERY, variable_values=variables)
            
            product = result.get('getProduct')
            if not product:
                return {'error': f'Product {product_id} not found'}
            
            # Format warehouse items
            warehouse_items = []
            total_stock = 0
            for item in product.get('warehouse_items', []):
                quantity = item.get('quantity', 0)
                total_stock += quantity
                warehouse_items.append({
                    'warehouse_number': item.get('warehouse_number'),
                    'quantity': quantity,
                    'status': item.get('status', {}).get('name', 'Unknown')
                })
            
            # Format attributes
            attributes = []
            for attr in product.get('attributes', []):
                attributes.append({
                    'title': attr.get('title'),
                    'values': attr.get('values', [])
                })
            
            return {
                'id': product['id'],
                'title': product.get('title'),
                'link': product.get('link'),
                'ean': product.get('ean'),
                'short_description': product.get('short'),
                'main_category': product.get('main_category', {}).get('title'),
                'total_stock': total_stock,
                'warehouse_items': warehouse_items,
                'attributes': attributes,
                'assigned_categories': [cat.get('title') for cat in product.get('assigned_categories', [])]
            }
            
        except Exception as e:
            logger.error(f"Error fetching product: {str(e)}")
            return {'error': f'Failed to fetch product: {str(e)}'}
    
    async def _list_warehouse_items(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List warehouse items with recent updates"""
        try:
            # Default to last 30 days
            if 'changed_from' in args and args['changed_from'] != "30 days ago":
                changed_from = args['changed_from'] + 'T00:00:00'
            else:
                changed_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%dT00:00:00')
            
            params = {
                'limit': min(args.get('limit', 30), 30)
            }
            
            variables = {
                'changed_from': changed_from,
                'params': params
            }
            
            async with self.client as session:
                result = await session.execute(WAREHOUSE_ITEMS_QUERY, variable_values=variables)
            
            items_data = result.get('getWarehouseItemsWithRecentStockUpdates', {})
            items = items_data.get('data', [])
            page_info = items_data.get('pageInfo', {})
            
            # Format items
            formatted_items = []
            for item in items:
                formatted_items.append({
                    'id': item['id'],
                    'ean': item.get('ean', ''),
                    'warehouse_number': item.get('warehouse_number'),
                    'quantity': item.get('quantity', 0),
                    'status': item.get('status', {}).get('name', 'Unknown'),
                    'weight': f"{item.get('weight', {}).get('value', 0)} {item.get('weight', {}).get('unit', '')}"
                })
            
            return {
                'items': formatted_items,
                'count': len(formatted_items),
                'has_more': page_info.get('hasNextPage', False),
                'changed_from': changed_from.split('T')[0]
            }
            
        except Exception as e:
            logger.error(f"Error listing warehouse items: {str(e)}")
            return {'error': f'Failed to list warehouse items: {str(e)}'}
    
    async def _get_warehouse_item(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get warehouse item details"""
        try:
            warehouse_number = args['warehouse_number']
            
            variables = {
                'warehouse_number': warehouse_number
            }
            
            async with self.client as session:
                result = await session.execute(WAREHOUSE_ITEM_DETAIL_QUERY, variable_values=variables)
            
            item = result.get('getWarehouseItem')
            if not item:
                return {'error': f'Warehouse item {warehouse_number} not found'}
            
            return {
                'id': item['id'],
                'warehouse_number': item['warehouse_number'],
                'ean': item.get('ean', ''),
                'quantity': item.get('quantity', 0),
                'status': item.get('status', {}).get('name', 'Unknown'),
                'weight': f"{item.get('weight', {}).get('value', 0)} {item.get('weight', {}).get('unit', '')}"
            }
            
        except Exception as e:
            logger.error(f"Error fetching warehouse item: {str(e)}")
            return {'error': f'Failed to fetch warehouse item: {str(e)}'}
    
    async def _list_invoices(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List invoices"""
        try:
            params = {
                'limit': min(args.get('limit', 30), 30),
                'order_by': 'pur_date',
                'sort': 'DESC'
            }
            
            filter_dict = {}
            if 'buy_date_from' in args:
                filter_dict['buy_date_from'] = args['buy_date_from']
            if 'buy_date_to' in args:
                filter_dict['buy_date_to'] = args['buy_date_to']
            
            variables = {
                'params': params
            }
            
            if filter_dict:
                variables['filter'] = filter_dict
            
            async with self.client as session:
                result = await session.execute(INVOICE_LIST_QUERY, variable_values=variables)
            
            invoices_data = result.get('getInvoiceList', {})
            invoices = invoices_data.get('data', [])
            page_info = invoices_data.get('pageInfo', {})
            
            # Format invoices
            formatted_invoices = []
            for invoice in invoices:
                customer = invoice.get('customer', {})
                customer_name = customer.get('company_name', '') or f"{customer.get('name', '')} {customer.get('surname', '')}".strip()
                
                formatted_invoices.append({
                    'id': invoice['id'],
                    'invoice_num': invoice['invoice_num'],
                    'order_num': invoice.get('order', {}).get('order_num'),
                    'customer': customer_name,
                    'total': f"{invoice.get('sum', {}).get('value')} {invoice.get('sum', {}).get('currency', {}).get('code')}",
                    'address': f"{invoice.get('invoice_address', {}).get('city', '')}, {invoice.get('invoice_address', {}).get('country', '')}"
                })
            
            return {
                'invoices': formatted_invoices,
                'count': len(formatted_invoices),
                'has_more': page_info.get('hasNextPage', False)
            }
            
        except Exception as e:
            logger.error(f"Error listing invoices: {str(e)}")
            return {'error': f'Failed to list invoices: {str(e)}'}
    
    async def _get_invoice(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get invoice details"""
        try:
            invoice_num = args['invoice_num']
            
            variables = {
                'invoice_num': invoice_num
            }
            
            async with self.client as session:
                result = await session.execute(INVOICE_DETAIL_QUERY, variable_values=variables)
            
            invoice = result.get('getInvoice')
            if not invoice:
                return {'error': f'Invoice {invoice_num} not found'}
            
            # Format customer
            customer = invoice.get('customer', {})
            customer_info = {
                'name': customer.get('company_name', '') or f"{customer.get('name', '')} {customer.get('surname', '')}".strip(),
                'company_id': customer.get('company_id'),
                'vat_id': customer.get('vat_id'),
                'email': customer.get('email')
            }
            
            # Format items
            items = []
            for item in invoice.get('items', []):
                items.append({
                    'label': item['item_label'],
                    'warehouse_number': item.get('warehouse_number'),
                    'ean': item.get('ean'),
                    'quantity': item['quantity'],
                    'price': f"{item.get('price', {}).get('value')} {item.get('price', {}).get('currency', {}).get('code')}"
                })
            
            return {
                'invoice_num': invoice['invoice_num'],
                'order_num': invoice.get('order', {}).get('order_num'),
                'supplier': invoice.get('supplier', {}).get('company_name'),
                'customer': customer_info,
                'items': items,
                'total': f"{invoice.get('sum', {}).get('value')} {invoice.get('sum', {}).get('currency', {}).get('code')}",
                'invoice_address': invoice.get('invoice_address', {})
            }
            
        except Exception as e:
            logger.error(f"Error fetching invoice: {str(e)}")
            return {'error': f'Failed to fetch invoice: {str(e)}'}
    
    async def _list_companies(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List companies (no general customer list available)"""
        try:
            variables = {}
            if 'name' in args:
                variables['name'] = args['name']
            
            async with self.client as session:
                result = await session.execute(COMPANIES_LIST_QUERY, variable_values=variables)
            
            companies = result.get('listMyCompanies', [])
            
            # Format companies
            formatted_companies = []
            for company in companies:
                formatted_companies.append({
                    'id': company['id'],
                    'name': company.get('company_name'),
                    'company_id': company.get('company_id'),
                    'vat_id': company.get('vat_id'),
                    'address': f"{company.get('street', '')}, {company.get('city', '')} {company.get('zip', '')}, {company.get('country', '')}"
                })
            
            return {
                'companies': formatted_companies,
                'count': len(formatted_companies)
            }
            
        except Exception as e:
            logger.error(f"Error listing companies: {str(e)}")
            return {'error': f'Failed to list companies: {str(e)}'}
    
    async def _get_order_statuses(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get order statuses"""
        try:
            lang_code = args.get('lang_code', 'SK')
            
            variables = {
                'lang_code': lang_code
            }
            
            async with self.client as session:
                result = await session.execute(ORDER_STATUSES_QUERY, variable_values=variables)
            
            statuses = result.get('listOrderStatuses', [])
            
            return {
                'statuses': [
                    {
                        'id': status['id'],
                        'name': status['name'],
                        'color': status.get('color')
                    }
                    for status in statuses
                ],
                'count': len(statuses)
            }
            
        except Exception as e:
            logger.error(f"Error fetching order statuses: {str(e)}")
            return {'error': f'Failed to fetch order statuses: {str(e)}'}
    
    async def _get_payment_methods(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get payment methods"""
        try:
            lang_code = args.get('lang_code', 'SK')
            
            variables = {
                'lang_code': lang_code
            }
            
            async with self.client as session:
                result = await session.execute(PAYMENT_METHODS_QUERY, variable_values=variables)
            
            payments = result.get('listPayments', [])
            
            return {
                'payment_methods': [
                    {
                        'id': payment['id'],
                        'name': payment['name'],
                        'price': f"{payment.get('price', {}).get('value', 0)} {payment.get('price', {}).get('currency', {}).get('code', '')}"
                    }
                    for payment in payments
                ],
                'count': len(payments)
            }
            
        except Exception as e:
            logger.error(f"Error fetching payment methods: {str(e)}")
            return {'error': f'Failed to fetch payment methods: {str(e)}'}
    
    async def _get_delivery_methods(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get delivery methods"""
        try:
            lang_code = args.get('lang_code', 'SK')
            
            variables = {
                'lang_code': lang_code
            }
            
            async with self.client as session:
                result = await session.execute(DELIVERY_METHODS_QUERY, variable_values=variables)
            
            shippings = result.get('listShippings', [])
            
            return {
                'delivery_methods': [
                    {
                        'id': shipping['id'],
                        'name': shipping['name'],
                        'price': f"{shipping.get('price', {}).get('value', 0)} {shipping.get('price', {}).get('currency', {}).get('code', '')}"
                    }
                    for shipping in shippings
                ],
                'count': len(shippings)
            }
            
        except Exception as e:
            logger.error(f"Error fetching delivery methods: {str(e)}")
            return {'error': f'Failed to fetch delivery methods: {str(e)}'}
    
    async def _get_currencies(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get currencies"""
        try:
            async with self.client as session:
                result = await session.execute(CURRENCIES_QUERY)
            
            currencies = result.get('listCurrencies', [])
            
            return {
                'currencies': [
                    {
                        'id': currency['id'],
                        'code': currency['code'],
                        'symbol': currency.get('symbol'),
                        'name': currency.get('name')
                    }
                    for currency in currencies
                ],
                'count': len(currencies)
            }
            
        except Exception as e:
            logger.error(f"Error fetching currencies: {str(e)}")
            return {'error': f'Failed to fetch currencies: {str(e)}'}
    
    async def _get_warehouse_statuses(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get warehouse statuses"""
        try:
            lang_code = args.get('lang_code', 'SK')
            
            variables = {
                'lang_code': lang_code
            }
            
            async with self.client as session:
                result = await session.execute(WAREHOUSE_STATUSES_QUERY, variable_values=variables)
            
            statuses = result.get('listWarehouseStatuses', [])
            
            return {
                'warehouse_statuses': [
                    {
                        'id': status['id'],
                        'name': status['name'],
                        'allow_order': status.get('allow_order', False)
                    }
                    for status in statuses
                ],
                'count': len(statuses)
            }
            
        except Exception as e:
            logger.error(f"Error fetching warehouse statuses: {str(e)}")
            return {'error': f'Failed to fetch warehouse statuses: {str(e)}'}
    
    async def run(self):
        """Run the MCP server"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="biznisweb-mcp",
                    server_version="0.2.0-hotfix",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )

def main():
    """Main entry point"""
    server = BiznisWebMCPServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()