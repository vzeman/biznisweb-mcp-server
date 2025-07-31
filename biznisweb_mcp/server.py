#!/usr/bin/env python3
"""
BizniWeb MCP Server

Provides tools for interacting with BizniWeb e-shop through GraphQL API
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

# Debug logging
import sys
print(f"DEBUG: Working directory: {os.getcwd()}", file=sys.stderr)
print(f"DEBUG: .env file exists: {os.path.exists('.env')}", file=sys.stderr)
print(f"DEBUG: API_TOKEN loaded: {'Yes' if API_TOKEN else 'No'}", file=sys.stderr)
print(f"DEBUG: API_URL: {API_URL}", file=sys.stderr)

# GraphQL Queries
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BizniWebMCPServer:
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
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls"""
            try:
                if not self.client:
                    await self._init_client()
                
                if name == "list_orders":
                    result = await self._list_orders(arguments)
                elif name == "get_order":
                    result = await self._get_order(arguments)
                elif name == "order_statistics":
                    result = await self._order_statistics(arguments)
                elif name == "search_orders":
                    result = await self._search_orders(arguments)
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
            logger.error(f"API_TOKEN is missing. Environment: {list(os.environ.keys())}")
            raise ValueError("BIZNISWEB_API_TOKEN not found in environment variables")
        
        transport = HTTPXAsyncTransport(
            url=API_URL,
            headers={
                'BW-API-Key': f'Token {API_TOKEN}',
                'Content-Type': 'application/json'
            }
        )
        self.client = Client(transport=transport, fetch_schema_from_transport=False)
    
    async def _list_orders(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List orders with optional filtering"""
        variables = {}
        
        # Add date filters - only use newer_from for start date
        # Note: The GraphQL API doesn't seem to support end date filtering directly,
        # so we'll filter by start date only and let the limit parameter control the range
        if 'from_date' in args:
            variables['newer_from'] = args['from_date'] + 'T00:00:00'
        
        # Add status if provided
        if 'status' in args:
            variables['status'] = args['status']
        
        # OrderParams for pagination/sorting
        variables['params'] = {
            'limit': args.get('limit', 30),
            'order_by': 'pur_date',
            'sort': 'DESC'
        }
        
        # If to_date is provided, we'll need to filter results client-side
        to_date_filter = None
        if 'to_date' in args:
            try:
                to_date_filter = datetime.strptime(args['to_date'], '%Y-%m-%d')
            except ValueError:
                logger.warning(f"Invalid to_date format: {args['to_date']}")
        
        async with self.client as session:
            result = await session.execute(ORDER_LIST_QUERY, variable_values=variables)
        
        orders_data = result.get('getOrderList', {})
        orders = orders_data.get('data', [])
        page_info = orders_data.get('pageInfo', {})
        
        # Apply client-side date filtering if to_date is specified
        if to_date_filter:
            filtered_orders = []
            for order in orders:
                try:
                    # Handle both date and datetime formats
                    order_date_str = order['pur_date'].split('T')[0] if 'T' in order['pur_date'] else order['pur_date'].split(' ')[0]
                    order_date = datetime.strptime(order_date_str, '%Y-%m-%d')
                    if order_date <= to_date_filter:
                        filtered_orders.append(order)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Error parsing order date for order {order.get('order_num', 'unknown')}: {e}")
                    continue
            orders = filtered_orders
        
        # Format orders for better readability
        formatted_orders = []
        for order in orders:
            try:
                customer = order.get('customer', {})
                customer_name = customer.get('company_name', '')
                if not customer_name:
                    customer_name = f"{customer.get('name', '')} {customer.get('surname', '')}".strip()
                
                # Safely get order sum and currency
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
        try:
            # Set default date range if not provided
            to_date = datetime.now()
            from_date = to_date - timedelta(days=30)
            
            if 'from_date' in args:
                from_date = datetime.strptime(args['from_date'], '%Y-%m-%d')
            if 'to_date' in args:
                to_date = datetime.strptime(args['to_date'], '%Y-%m-%d')
            
            logger.info(f"Fetching order statistics from {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}")
            
            # Fetch all orders in date range
            all_orders = []
            has_next = True
            cursor = None
            total_fetched = 0
            
            while has_next:
                params = {
                    'limit': 30,  # Maximum supported by the API
                    'order_by': 'pur_date',
                    'sort': 'DESC'  # Use DESC as that's what works
                }
                if cursor:
                    params['cursor'] = cursor
                
                # Prepare variables
                variables = {
                    'params': params
                }
                
                # Try with newer_from first, fallback to no date filter if it fails
                try:
                    variables['newer_from'] = from_date.strftime('%Y-%m-%dT00:00:00')
                    
                    async with self.client as session:
                        result = await session.execute(ORDER_LIST_QUERY, variable_values=variables)
                        
                except Exception as e:
                    logger.warning(f"Query with newer_from failed, trying without date filter: {e}")
                    # Remove the date filter and fetch all recent orders
                    variables = {
                        'params': params
                    }
                    
                    async with self.client as session:
                        result = await session.execute(ORDER_LIST_QUERY, variable_values=variables)
                
                orders_data = result.get('getOrderList', {})
                orders = orders_data.get('data', [])
                
                # Filter orders by date range client-side
                filtered_orders = []
                for order in orders:
                    try:
                        # Handle both date and datetime formats
                        order_date_str = order['pur_date'].split('T')[0] if 'T' in order['pur_date'] else order['pur_date'].split(' ')[0]
                        order_date = datetime.strptime(order_date_str, '%Y-%m-%d')
                        
                        # Check both start and end date
                        if order_date >= from_date and order_date <= to_date:
                            filtered_orders.append(order)
                        elif order_date < from_date:
                            # Since orders are sorted by date DESC (newest first), 
                            # if we hit an order older than from_date, we can stop
                            has_next = False
                            break
                        # If order_date > to_date, just continue (too new, but keep going since DESC)
                            
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Error parsing order date for statistics: {e}")
                        continue
                
                all_orders.extend(filtered_orders)
                total_fetched += len(orders)
                
                # Safety check to prevent infinite loops
                if total_fetched > 10000:
                    logger.warning("Reached maximum fetch limit of 10000 orders for statistics")
                    break
                
                page_info = orders_data.get('pageInfo', {})
                has_next = has_next and page_info.get('hasNextPage', False)
                cursor = page_info.get('nextCursor')
                
                logger.debug(f"Fetched batch: {len(orders)} orders, total so far: {len(all_orders)}")
        
        except Exception as e:
            logger.error(f"Error fetching orders for statistics: {str(e)}")
            return {
                'error': f'Failed to fetch orders: {str(e)}',
                'period': {
                    'from': from_date.strftime('%Y-%m-%d') if 'from_date' in locals() else None,
                    'to': to_date.strftime('%Y-%m-%d') if 'to_date' in locals() else None
                }
            }
        
        # Define excluded statuses
        excluded_statuses = [
            'Storno',
            'Platba online - platnosť vypršala',
            'Platba online - platba zamietnutá',
            'Čaká na úhradu',
            'GoPay - platebni metoda potvrzena'
        ]
        
        logger.info(f"Processing {len(all_orders)} orders for statistics calculation")
        
        # Calculate statistics
        total_revenue = 0
        total_items = 0
        status_counts = {}
        daily_stats = {}
        valid_orders_count = 0
        
        for order in all_orders:
            try:
                # Skip orders with excluded statuses
                status_name = order.get('status', {}).get('name', '')
                if status_name in excluded_statuses:
                    logger.debug(f"Skipping order {order.get('order_num', 'unknown')} with excluded status: {status_name}")
                    continue
                
                # Safely extract order value
                order_sum = order.get('sum', {})
                order_value = order_sum.get('value', 0)
                
                # Convert to float if it's a string
                if isinstance(order_value, str):
                    try:
                        order_value = float(order_value)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid order value '{order_value}' for order {order.get('order_num', 'unknown')}")
                        order_value = 0
                
                total_revenue += order_value
                valid_orders_count += 1
                
                items_count = len(order.get('items', []))
                total_items += items_count
                
                # Count by status
                status = order.get('status', {}).get('name', 'Unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
                
                # Daily statistics
                order_date = order['pur_date'].split('T')[0] if 'T' in order['pur_date'] else order['pur_date'].split(' ')[0]
                if order_date not in daily_stats:
                    daily_stats[order_date] = {
                        'orders': 0,
                        'revenue': 0,
                        'items': 0
                    }
                daily_stats[order_date]['orders'] += 1
                daily_stats[order_date]['revenue'] += order_value
                daily_stats[order_date]['items'] += items_count
                
            except Exception as e:
                logger.error(f"Error processing order {order.get('order_num', 'unknown')}: {str(e)}")
                continue
        
        logger.info(f"Processed {valid_orders_count} valid orders, total revenue: {total_revenue}")
        
        return {
            'period': {
                'from': from_date.strftime('%Y-%m-%d'),
                'to': to_date.strftime('%Y-%m-%d')
            },
            'summary': {
                'total_orders': len(all_orders),
                'valid_orders': valid_orders_count,
                'excluded_orders': len(all_orders) - valid_orders_count,
                'total_revenue': round(total_revenue, 2),
                'total_items': total_items,
                'average_order_value': round(total_revenue / valid_orders_count, 2) if valid_orders_count > 0 else 0
            },
            'status_breakdown': status_counts,
            'daily_stats': daily_stats,
            'excluded_statuses': excluded_statuses
        }
    
    async def _search_orders(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search orders by customer or order number"""
        query = args['query'].lower()
        
        # Fetch recent orders and search
        variables = {
            'params': {
                'limit': 100,
                'order_by': 'pur_date',
                'sort': 'DESC'
            }
        }
        
        async with self.client as session:
            result = await session.execute(ORDER_LIST_QUERY, variable_values=variables)
        
        orders = result.get('getOrderList', {}).get('data', [])
        
        # Search in orders
        matching_orders = []
        for order in orders:
            # Check order number
            if query in order['order_num'].lower():
                matching_orders.append(order)
                continue
            
            # Check customer name/email
            customer = order.get('customer', {})
            customer_name = customer.get('company_name', '') or f"{customer.get('name', '')} {customer.get('surname', '')}".strip()
            customer_email = customer.get('email', '')
            
            if query in customer_name.lower() or query in customer_email.lower():
                matching_orders.append(order)
        
        # Format results
        formatted_results = []
        for order in matching_orders[:20]:  # Limit to 20 results
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
    
    async def run(self):
        """Run the MCP server"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="biznisweb-mcp",
                    server_version="0.1.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )

def main():
    """Main entry point"""
    server = BizniWebMCPServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()