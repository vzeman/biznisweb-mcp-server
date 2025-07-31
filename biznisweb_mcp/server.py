#!/usr/bin/env python3
"""
BiznisWeb MCP Server

Provides tools for interacting with BiznisWeb e-shop through GraphQL API
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

WAREHOUSE_ITEM_LIST_QUERY = gql("""
query GetWarehouseItemList($params: WarehouseItemParams) {
  getWarehouseItemList(params: $params) {
    data {
      id
      name
      sku
      ean
      description
      category {
        id
        name
      }
      price {
        value
        currency {
          code
        }
      }
      stock_quantity
      reserved_quantity
      available_quantity
      location
      last_updated
    }
    pageInfo {
      hasNextPage
      nextCursor
      totalPages
    }
  }
}
""")

WAREHOUSE_ITEM_DETAIL_QUERY = gql("""
query GetWarehouseItem($id: ID!) {
  getWarehouseItem(id: $id) {
    id
    name
    sku
    ean
    description
    category {
      id
      name
    }
    price {
      value
      formatted
      currency {
        code
        symbol
      }
    }
    stock_quantity
    reserved_quantity
    available_quantity
    location
    weight
    dimensions {
      length
      width
      height
      unit
    }
    supplier {
      id
      name
      contact_email
    }
    last_updated
    created_at
  }
}
""")

STOCK_INFO_QUERY = gql("""
query GetStockInfo($product_ids: [ID!]!) {
  getStockInfo(product_ids: $product_ids) {
    product_id
    sku
    name
    stock_quantity
    reserved_quantity
    available_quantity
    location
    last_stock_movement {
      date
      type
      quantity
      reason
    }
    reorder_level
    reorder_quantity
  }
}
""")

UPDATE_WAREHOUSE_ITEM_MUTATION = gql("""
mutation UpdateWarehouseItem($input: WarehouseItemInput!) {
  updateWarehouseItem(input: $input) {
    id
    name
    sku
    stock_quantity
    available_quantity
    location
    last_updated
  }
}
""")

# Invoice Management Queries
INVOICE_LIST_QUERY = gql("""
query GetInvoiceList($params: InvoiceParams, $filter: InvoiceFilter) {
  getInvoiceList(params: $params, filter: $filter) {
    data {
      id
      invoice_num
      issue_date
      due_date
      vat_date
      status
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
    }
    pageInfo {
      hasNextPage
      nextCursor
      totalPages
    }
  }
}
""")

INVOICE_DETAIL_QUERY = gql("""
query GetInvoice($id: ID!) {
  getInvoice(id: $id) {
    id
    invoice_num
    issue_date
    due_date
    vat_date
    status
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
    items {
      item_label
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
    order {
      order_num
    }
  }
}
""")

CREATE_INVOICE_MUTATION = gql("""
mutation CreateInvoice($order_id: ID!) {
  createInvoice(order_id: $order_id) {
    id
    invoice_num
    issue_date
    due_date
    status
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

PROFORMA_INVOICE_QUERY = gql("""
query GetProformaInvoice($id: ID!) {
  getProformaInvoice(id: $id) {
    id
    invoice_num
    issue_date
    due_date
    vat_date
    status
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
    items {
      item_label
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
    order {
      order_num
    }
  }
}
""")

CREDIT_NOTE_LIST_QUERY = gql("""
query GetCreditNoteList($params: CreditNoteParams) {
  getCreditNoteList(params: $params) {
    data {
      id
      credit_note_num
      issue_date
      status
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
    }
    pageInfo {
      hasNextPage
      nextCursor
      totalPages
    }
  }
}
""")

CREDIT_NOTE_DETAIL_QUERY = gql("""
query GetCreditNote($id: ID!) {
  getCreditNote(id: $id) {
    id
    credit_note_num
    issue_date
    status
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
    items {
      item_label
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
    invoice {
      invoice_num
    }
  }
}
""")

# Configuration & Lookup Queries
ORDER_STATUSES_QUERY = gql("""
query GetOrderStatuses {
  getOrderStatuses {
    id
    name
    description
    color
    is_active
    sort_order
  }
}
""")

PAYMENT_METHODS_QUERY = gql("""
query GetPaymentMethods {
  getPaymentMethods {
    id
    name
    description
    is_active
    sort_order
    settings {
      key
      value
    }
  }
}
""")

DELIVERY_METHODS_QUERY = gql("""
query GetDeliveryMethods {
  getDeliveryMethods {
    id
    name
    description
    price {
      value
      currency {
        code
      }
    }
    is_active
    sort_order
    settings {
      key
      value
    }
  }
}
""")

COUNTRIES_QUERY = gql("""
query GetCountries {
  getCountries {
    id
    name
    code
    iso_code
    is_active
    sort_order
  }
}
""")

CURRENCIES_QUERY = gql("""
query GetCurrencies {
  getCurrencies {
    id
    name
    code
    symbol
    exchange_rate
    is_default
    is_active
  }
}
""")

# Mutation Queries
UPDATE_ORDER_STATUS_MUTATION = gql("""
mutation UpdateOrderStatus($order_id: ID!, $status_id: ID!) {
  updateOrderStatus(order_id: $order_id, status_id: $status_id) {
    id
    order_num
    status {
      id
      name
    }
    last_change
  }
}
""")

CREATE_PRODUCT_PACKAGE_MUTATION = gql("""
mutation CreateProductPackage($input: ProductPackageInput!) {
  createProductPackage(input: $input) {
    id
    name
    description
    products {
      product_id
      quantity
    }
    price {
      value
      currency {
        code
      }
    }
    is_active
    created_at
  }
}
""")

UPDATE_PRODUCT_AVAILABILITY_MUTATION = gql("""
mutation UpdateProductAvailability($product_id: ID!, $availability: AvailabilityInput!) {
  updateProductAvailability(product_id: $product_id, availability: $availability) {
    product_id
    is_available
    stock_quantity
    available_quantity
    availability_text
    delivery_date
    last_updated
  }
}
""")

CUSTOMER_LIST_QUERY = gql("""
query GetCustomerList($params: CustomerParams, $filter: CustomerFilter) {
  getCustomerList(params: $params, filter: $filter) {
    data {
      id
      name
      surname
      company_name
      email
      phone
      company_id
      vat_id
      registration_date
      last_order_date
      total_orders
      total_spent {
        value
        currency {
          code
        }
      }
      address {
        street
        city
        zip
        country
      }
      customer_type
      status
    }
    pageInfo {
      hasNextPage
      nextCursor
      totalPages
    }
  }
}
""")

CUSTOMER_DETAIL_QUERY = gql("""
query GetCustomer($id: ID!) {
  getCustomer(id: $id) {
    id
    name
    surname
    company_name
    email
    phone
    company_id
    vat_id
    registration_date
    last_order_date
    last_login_date
    total_orders
    total_spent {
      value
      formatted
      currency {
        code
        symbol
      }
    }
    address {
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
    customer_type
    status
    preferences {
      newsletter_subscription
      marketing_emails
      language
    }
    notes
    recent_orders {
      id
      order_num
      pur_date
      status {
        id
        name
      }
      sum {
        value
        formatted
        currency {
          code
        }
      }
    }
  }
}
""")

CATEGORY_TREE_QUERY = gql("""
query GetCategoryTree($params: CategoryParams) {
  getCategoryTree(params: $params) {
    id
    name
    slug
    description
    parent_id
    level
    position
    is_active
    product_count
    image_url
    seo_title
    seo_description
    created_at
    updated_at
    children {
      id
      name
      slug
      description
      parent_id
      level
      position
      is_active
      product_count
      image_url
      children {
        id
        name
        slug
        description
        parent_id
        level
        position
        is_active
        product_count
        image_url
      }
    }
  }
}
""")

# Product Management GraphQL Queries
PRODUCT_LIST_QUERY = gql("""
query GetProductList($params: ProductListParams, $filter: ProductListFilter) {
  getProductList(params: $params, filter: $filter) {
    data {
      id
      name
      sku
      ean
      description
      category {
        id
        name
      }
      price {
        value
        formatted
        currency {
          code
          symbol
        }
      }
      stock_quantity
      available_quantity
      images {
        url
        alt
      }
      created_at
      updated_at
    }
    pageInfo {
      hasNextPage
      nextCursor
      totalPages
    }
  }
}
""")

PRODUCT_DETAIL_QUERY = gql("""
query GetProduct($id: ID!, $lang_code: String) {
  getProduct(id: $id, lang_code: $lang_code) {
    id
    name
    sku
    ean
    description
    long_description
    category {
      id
      name
      path
    }
    price {
      value
      formatted
      currency {
        code
        symbol
      }
    }
    stock_quantity
    available_quantity
    weight
    dimensions {
      length
      width
      height
      unit
    }
    attributes {
      name
      value
    }
    images {
      url
      alt
      title
    }
    tags
    meta {
      title
      description
      keywords
    }
    created_at
    updated_at
  }
}
""")

PRODUCT_SEARCH_QUERY = gql("""
query SearchProductList($search_term: String!, $params: ProductListParams) {
  searchProductList(search_term: $search_term, params: $params) {
    data {
      id
      name
      sku
      ean
      description
      category {
        id
        name
      }
      price {
        value
        formatted
        currency {
          code
          symbol
        }
      }
      stock_quantity
      available_quantity
      images {
        url
        alt
      }
      relevance_score
    }
    pageInfo {
      hasNextPage
      nextCursor
      totalPages
    }
  }
}
""")

PRODUCT_VARIANTS_QUERY = gql("""
query GetProductVariants($product_id: ID!) {
  getProductVariants(product_id: $product_id) {
    id
    name
    sku
    ean
    variant_type
    variant_options {
      name
      value
    }
    price {
      value
      formatted
      currency {
        code
        symbol
      }
    }
    stock_quantity
    available_quantity
    images {
      url
      alt
    }
    parent_product_id
  }
}
""")

PRODUCT_AVAILABILITY_QUERY = gql("""
query GetProductAvailability($product_id: ID!) {
  getProductAvailability(product_id: $product_id) {
    product_id
    sku
    name
    stock_quantity
    available_quantity
    reserved_quantity
    availability_status
    estimated_restock_date
    supplier_stock
    backorder_allowed
    min_order_quantity
    max_order_quantity
    location
    last_stock_update
  }
}
""")

RELATED_PRODUCTS_QUERY = gql("""
query GetRelatedProducts($product_id: ID!, $type: String) {
  getRelatedProducts(product_id: $product_id, type: $type) {
    id
    name
    sku
    description
    category {
      id
      name
    }
    price {
      value
      formatted
      currency {
        code
        symbol
      }
    }
    stock_quantity
    available_quantity
    images {
      url
      alt
    }
    relation_type
    relation_score
  }
}
""")

PRODUCT_PRICES_QUERY = gql("""
query GetProductPrices($product_id: ID!) {
  getProductPrices(product_id: $product_id) {
    product_id
    sku
    name
    base_price {
      value
      formatted
      currency {
        code
        symbol
      }
    }
    sale_price {
      value
      formatted
      currency {
        code
        symbol
      }
    }
    discount_amount {
      value
      percentage
    }
    price_tiers {
      min_quantity
      price {
        value
        formatted
      }
    }
    tax_rate
    price_includes_tax
    valid_from
    valid_to
    promotional_price {
      value
      formatted
      valid_from
      valid_to
    }
  }
}
""")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                # Product Management Tools
                Tool(
                    name="list_products",
                    description="List products with optional filtering and pagination",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "category_id": {
                                "type": "integer",
                                "description": "Filter by category ID"
                            },
                            "in_stock_only": {
                                "type": "boolean",
                                "description": "Show only products in stock",
                                "default": False
                            },
                            "min_price": {
                                "type": "number",
                                "description": "Minimum price filter"
                            },
                            "max_price": {
                                "type": "number",
                                "description": "Maximum price filter"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of products to return",
                                "default": 30
                            },
                            "sort_by": {
                                "type": "string",
                                "description": "Sort field (name, price, created_at)",
                                "default": "name"
                            },
                            "sort_order": {
                                "type": "string",
                                "description": "Sort order (ASC, DESC)",
                                "default": "ASC"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_product",
                    description="Get detailed information about a specific product",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "string",
                                "description": "Product ID"
                            },
                            "lang_code": {
                                "type": "string",
                                "description": "Language code (e.g., 'en', 'sk')",
                                "default": "sk"
                            }
                        },
                        "required": ["product_id"]
                    }
                ),
                Tool(
                    name="search_products",
                    description="Full-text search for products",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "search_term": {
                                "type": "string",
                                "description": "Search query"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "default": 30
                            },
                            "sort_by": {
                                "type": "string",
                                "description": "Sort field (relevance, name, price)",
                                "default": "relevance"
                            }
                        },
                        "required": ["search_term"]
                    }
                ),
                Tool(
                    name="get_product_variants",
                    description="Get all variants of a specific product",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "string",
                                "description": "Product ID"
                            }
                        },
                        "required": ["product_id"]
                    }
                ),
                Tool(
                    name="get_product_availability",
                    description="Check product stock and availability status",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "string",
                                "description": "Product ID"
                            }
                        },
                        "required": ["product_id"]
                    }
                ),
                Tool(
                    name="get_related_products",
                    description="Get related or recommended products",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "string",
                                "description": "Product ID"
                            },
                            "relation_type": {
                                "type": "string",
                                "description": "Type of relation (related, recommended, similar, accessories)",
                                "default": "related"
                            }
                        },
                        "required": ["product_id"]
                    }
                ),
                Tool(
                    name="get_product_prices",
                    description="Get detailed pricing information for a product",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "string",
                                "description": "Product ID"
                            }
                        },
                        "required": ["product_id"]
                    }
                ),
                Tool(
                    name="list_warehouse_items",
                    description="List warehouse items with optional filtering and pagination",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Filter by category name or ID"
                            },
                            "search": {
                                "type": "string",
                                "description": "Search in item name, SKU, or EAN"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of items to return",
                                "default": 30
                            },
                            "low_stock": {
                                "type": "boolean",
                                "description": "Filter items with low stock levels"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_warehouse_item",
                    description="Get detailed information about a specific warehouse item",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Warehouse item ID"
                            }
                        },
                        "required": ["id"]
                    }
                ),
                Tool(
                    name="get_stock_info",
                    description="Get stock information for one or more products",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "product_ids": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                                "description": "List of product IDs to get stock info for"
                            }
                        },
                        "required": ["product_ids"]
                    }
                ),
                Tool(
                    name="update_warehouse_item",
                    description="Update warehouse item information (mutation)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Warehouse item ID"
                            },
                            "name": {
                                "type": "string",
                                "description": "Item name"
                            },
                            "stock_quantity": {
                                "type": "integer",
                                "description": "New stock quantity"
                            },
                            "location": {
                                "type": "string",
                                "description": "Storage location"
                            },
                            "price": {
                                "type": "number",
                                "description": "Item price"
                            }
                        },
                        "required": ["id"]
                    }
                ),
                # Configuration & Lookup Tools
                Tool(
                    name="get_order_statuses",
                    description="Get list of order statuses",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="get_payment_methods",
                    description="Get available payment methods",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="get_delivery_methods",
                    description="Get available delivery methods",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="get_countries",
                    description="Get list of countries",
                    inputSchema={
                        "type": "object",
                        "properties": {}
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
                    name="update_order_status",
                    description="Update order status (mutation)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "string",
                                "description": "Order ID"
                            },
                            "status_id": {
                                "type": "string",
                                "description": "New status ID"
                            }
                        },
                        "required": ["order_id", "status_id"]
                    }
                ),
                Tool(
                    name="create_product_package",
                    description="Create product package (mutation)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Package name"
                            },
                            "description": {
                                "type": "string",
                                "description": "Package description"
                            },
                            "products": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "product_id": {
                                            "type": "string",
                                            "description": "Product ID"
                                        },
                                        "quantity": {
                                            "type": "integer",
                                            "description": "Product quantity in package"
                                        }
                                    },
                                    "required": ["product_id", "quantity"]
                                },
                                "description": "List of products in the package"
                            },
                            "price": {
                                "type": "number",
                                "description": "Package price"
                            },
                            "currency_code": {
                                "type": "string",
                                "description": "Currency code (e.g., 'EUR', 'USD')",
                                "default": "EUR"
                            },
                            "is_active": {
                                "type": "boolean",
                                "description": "Whether the package is active",
                                "default": True
                            }
                        },
                        "required": ["name", "products", "price"]
                    }
                ),
                Tool(
                    name="update_product_availability",
                    description="Update product availability (mutation)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "string",
                                "description": "Product ID"
                            },
                            "is_available": {
                                "type": "boolean",
                                "description": "Whether the product is available"
                            },
                            "stock_quantity": {
                                "type": "integer",
                                "description": "Stock quantity"
                            },
                            "availability_text": {
                                "type": "string",
                                "description": "Custom availability text"
                            },
                            "delivery_date": {
                                "type": "string",
                                "description": "Expected delivery date (YYYY-MM-DD format)"
                            }
                        },
                        "required": ["product_id"]
                    }
                ),
                # Invoice Management Tools
                Tool(
                    name="list_invoices",
                    description="List invoices with optional filtering and pagination",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "from_date": {
                                "type": "string",
                                "description": "From date in YYYY-MM-DD format (issue date)"
                            },
                            "to_date": {
                                "type": "string",
                                "description": "To date in YYYY-MM-DD format (issue date)"
                            },
                            "status": {
                                "type": "string",
                                "description": "Invoice status"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of invoices to return",
                                "default": 30
                            }
                        }
                    }
                ),
                Tool(
                    name="get_invoice",
                    description="Get detailed information about a specific invoice",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "invoice_id": {
                                "type": "string",
                                "description": "Invoice ID"
                            }
                        },
                        "required": ["invoice_id"]
                    }
                ),
                Tool(
                    name="create_invoice",
                    description="Create new invoice from an existing order (mutation)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "order_id": {
                                "type": "string",
                                "description": "Order ID to create invoice from"
                            }
                        },
                        "required": ["order_id"]
                    }
                ),
                Tool(
                    name="get_proforma_invoice",
                    description="Get detailed information about a specific proforma invoice",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "proforma_id": {
                                "type": "string",
                                "description": "Proforma invoice ID"
                            }
                        },
                        "required": ["proforma_id"]
                    }
                ),
                Tool(
                    name="list_credit_notes",
                    description="List credit notes with optional filtering and pagination",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "from_date": {
                                "type": "string",
                                "description": "From date in YYYY-MM-DD format (issue date)"
                            },
                            "to_date": {
                                "type": "string",
                                "description": "To date in YYYY-MM-DD format (issue date)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of credit notes to return",
                                "default": 30
                            }
                        }
                    }
                ),
                Tool(
                    name="get_credit_note",
                    description="Get detailed information about a specific credit note",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "credit_note_id": {
                                "type": "string",
                                "description": "Credit note ID"
                            }
                        },
                        "required": ["credit_note_id"]
                    }
                ),
                # Customer & Category Management Tools
                Tool(
                    name="list_customers",
                    description="List customers with optional search and filtering",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "search": {
                                "type": "string",
                                "description": "Search in customer name, email, company name"
                            },
                            "customer_type": {
                                "type": "string",
                                "description": "Filter by customer type (person, company)"
                            },
                            "status": {
                                "type": "string",
                                "description": "Filter by customer status (active, inactive)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of customers to return",
                                "default": 30
                            },
                            "sort_by": {
                                "type": "string",
                                "description": "Sort field (name, registration_date, last_order_date, total_spent)",
                                "default": "name"
                            },
                            "sort_order": {
                                "type": "string",
                                "description": "Sort order (ASC, DESC)",
                                "default": "ASC"
                            }
                        }
                    }
                ),
                Tool(
                    name="get_customer",
                    description="Get detailed information about a specific customer",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "customer_id": {
                                "type": "string",
                                "description": "Customer ID"
                            }
                        },
                        "required": ["customer_id"]
                    }
                ),
                Tool(
                    name="get_categories",
                    description="Get product category tree with hierarchical structure",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "parent_id": {
                                "type": "string",
                                "description": "Get categories under specific parent (null for root categories)"
                            },
                            "max_depth": {
                                "type": "integer",
                                "description": "Maximum depth of category tree to return",
                                "default": 3
                            },
                            "include_inactive": {
                                "type": "boolean",
                                "description": "Include inactive categories",
                                "default": False
                            },
                            "include_empty": {
                                "type": "boolean",
                                "description": "Include categories with no products",
                                "default": False
                            }
                        }
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
                # Product Management Tools
                elif name == "list_products":
                    result = await self._list_products(arguments)
                elif name == "get_product":
                    result = await self._get_product(arguments)
                elif name == "search_products":
                    result = await self._search_products(arguments)
                elif name == "get_product_variants":
                    result = await self._get_product_variants(arguments)
                elif name == "get_product_availability":
                    result = await self._get_product_availability(arguments)
                elif name == "get_related_products":
                    result = await self._get_related_products(arguments)
                elif name == "get_product_prices":
                    result = await self._get_product_prices(arguments)
                elif name == "list_warehouse_items":
                    result = await self._list_warehouse_items(arguments)
                elif name == "get_warehouse_item":
                    result = await self._get_warehouse_item(arguments)
                elif name == "get_stock_info":
                    result = await self._get_stock_info(arguments)
                elif name == "update_warehouse_item":
                    result = await self._update_warehouse_item(arguments)
                # Configuration & Lookup Tools
                elif name == "get_order_statuses":
                    result = await self._get_order_statuses(arguments)
                elif name == "get_payment_methods":
                    result = await self._get_payment_methods(arguments)
                elif name == "get_delivery_methods":
                    result = await self._get_delivery_methods(arguments)
                elif name == "get_countries":
                    result = await self._get_countries(arguments)
                elif name == "get_currencies":
                    result = await self._get_currencies(arguments)
                elif name == "update_order_status":
                    result = await self._update_order_status(arguments)
                elif name == "create_product_package":
                    result = await self._create_product_package(arguments)
                elif name == "update_product_availability":
                    result = await self._update_product_availability(arguments)
                # Invoice Management Tools
                elif name == "list_invoices":
                    result = await self._list_invoices(arguments)
                elif name == "get_invoice":
                    result = await self._get_invoice(arguments)
                elif name == "create_invoice":
                    result = await self._create_invoice(arguments)
                elif name == "get_proforma_invoice":
                    result = await self._get_proforma_invoice(arguments)
                elif name == "list_credit_notes":
                    result = await self._list_credit_notes(arguments)
                elif name == "get_credit_note":
                    result = await self._get_credit_note(arguments)
                # Customer & Category Management Tools
                elif name == "list_customers":
                    result = await self._list_customers(arguments)
                elif name == "get_customer":
                    result = await self._get_customer(arguments)
                elif name == "get_categories":
                    result = await self._get_categories(arguments)
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
    
    # Product Management Handler Methods
    async def _list_products(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List products with optional filtering and pagination"""
        variables = {}
        
        # ProductListParams for pagination/sorting
        params = {
            'limit': args.get('limit', 30),
            'order_by': args.get('sort_by', 'name'),
            'sort': args.get('sort_order', 'ASC')
        }
        variables['params'] = params
        
        # ProductListFilter for filtering
        filter_params = {}
        
        if 'category_id' in args:
            filter_params['category_id'] = args['category_id']
        if 'in_stock_only' in args and args['in_stock_only']:
            filter_params['in_stock_only'] = True
        if 'min_price' in args:
            filter_params['min_price'] = args['min_price']
        if 'max_price' in args:
            filter_params['max_price'] = args['max_price']
            
        if filter_params:
            variables['filter'] = filter_params
        
        try:
            async with self.client as session:
                result = await session.execute(PRODUCT_LIST_QUERY, variable_values=variables)
        except Exception as e:
            logger.error(f"Error fetching product list: {str(e)}")
            return {'error': f'Failed to fetch products: {str(e)}'}
        
        products_data = result.get('getProductList', {})
        products = products_data.get('data', [])
        page_info = products_data.get('pageInfo', {})
        
        # Format products for better readability
        formatted_products = []
        for product in products:
            try:
                category = product.get('category', {})
                price = product.get('price', {})
                images = product.get('images', [])
                
                formatted_products.append({
                    'id': product['id'],
                    'name': product['name'],
                    'sku': product.get('sku'),
                    'ean': product.get('ean'),
                    'description': product.get('description'),
                    'category': category.get('name') if category else None,
                    'price': price.get('formatted') if price else None,
                    'currency': price.get('currency', {}).get('code') if price else None,
                    'stock_quantity': product.get('stock_quantity'),
                    'available_quantity': product.get('available_quantity'),
                    'image_url': images[0].get('url') if images else None,
                    'created_at': product.get('created_at'),
                    'updated_at': product.get('updated_at')
                })
            except Exception as e:
                logger.error(f"Error formatting product {product.get('id', 'unknown')}: {e}")
                continue
        
        return {
            'products': formatted_products,
            'count': len(formatted_products),
            'has_more': page_info.get('hasNextPage', False),
            'total_pages': page_info.get('totalPages')
        }
    
    async def _get_product(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed product information"""
        product_id = args['product_id']
        lang_code = args.get('lang_code', 'sk')
        
        try:
            async with self.client as session:
                result = await session.execute(PRODUCT_DETAIL_QUERY, variable_values={
                    'id': product_id,
                    'lang_code': lang_code
                })
        except Exception as e:
            logger.error(f"Error fetching product {product_id}: {str(e)}")
            return {'error': f'Failed to fetch product: {str(e)}'}
        
        product = result.get('getProduct')
        if not product:
            return {'error': f'Product {product_id} not found'}
        
        # Format the product data
        category = product.get('category', {})
        price = product.get('price', {})
        dimensions = product.get('dimensions', {})
        attributes = product.get('attributes', [])
        images = product.get('images', [])
        meta = product.get('meta', {})
        
        return {
            'id': product['id'],
            'name': product['name'],
            'sku': product.get('sku'),
            'ean': product.get('ean'),
            'description': product.get('description'),
            'long_description': product.get('long_description'),
            'category': {
                'id': category.get('id'),
                'name': category.get('name'),
                'path': category.get('path')
            } if category else None,
            'price': {
                'value': price.get('value'),
                'formatted': price.get('formatted'),
                'currency': price.get('currency', {}).get('code') if price.get('currency') else None
            } if price else None,
            'stock_quantity': product.get('stock_quantity'),
            'available_quantity': product.get('available_quantity'),
            'weight': product.get('weight'),
            'dimensions': {
                'length': dimensions.get('length'),
                'width': dimensions.get('width'),
                'height': dimensions.get('height'),
                'unit': dimensions.get('unit')
            } if dimensions else None,
            'attributes': [{'name': attr.get('name'), 'value': attr.get('value')} for attr in attributes],
            'images': [{'url': img.get('url'), 'alt': img.get('alt'), 'title': img.get('title')} for img in images],
            'tags': product.get('tags', []),
            'meta': {
                'title': meta.get('title'),
                'description': meta.get('description'),
                'keywords': meta.get('keywords')
            } if meta else None,
            'created_at': product.get('created_at'),
            'updated_at': product.get('updated_at')
        }
    
    async def _search_products(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Full-text search for products"""
        search_term = args['search_term']
        
        # ProductListParams for pagination/sorting
        params = {
            'limit': args.get('limit', 30),
            'order_by': args.get('sort_by', 'relevance'),
            'sort': 'DESC' if args.get('sort_by') == 'relevance' else 'ASC'
        }
        
        try:
            async with self.client as session:
                result = await session.execute(PRODUCT_SEARCH_QUERY, variable_values={
                    'search_term': search_term,
                    'params': params
                })
        except Exception as e:
            logger.error(f"Error searching products with term '{search_term}': {str(e)}")
            return {'error': f'Failed to search products: {str(e)}'}
        
        products_data = result.get('searchProductList', {})
        products = products_data.get('data', [])
        page_info = products_data.get('pageInfo', {})
        
        # Format search results
        formatted_results = []
        for product in products:
            try:
                category = product.get('category', {})
                price = product.get('price', {})
                images = product.get('images', [])
                
                formatted_results.append({
                    'id': product['id'],
                    'name': product['name'],
                    'sku': product.get('sku'),
                    'ean': product.get('ean'),
                    'description': product.get('description'),
                    'category': category.get('name') if category else None,
                    'price': price.get('formatted') if price else None,
                    'currency': price.get('currency', {}).get('code') if price else None,
                    'stock_quantity': product.get('stock_quantity'),
                    'available_quantity': product.get('available_quantity'),
                    'image_url': images[0].get('url') if images else None,
                    'relevance_score': product.get('relevance_score')
                })
            except Exception as e:
                logger.error(f"Error formatting search result {product.get('id', 'unknown')}: {e}")
                continue
        
        return {
            'search_term': search_term,
            'results': formatted_results,
            'count': len(formatted_results),
            'has_more': page_info.get('hasNextPage', False),
            'total_pages': page_info.get('totalPages')
        }
    
    async def _get_product_variants(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get all variants of a specific product"""
        product_id = args['product_id']
        
        try:
            async with self.client as session:
                result = await session.execute(PRODUCT_VARIANTS_QUERY, variable_values={
                    'product_id': product_id
                })
        except Exception as e:
            logger.error(f"Error fetching variants for product {product_id}: {str(e)}")
            return {'error': f'Failed to fetch product variants: {str(e)}'}
        
        variants = result.get('getProductVariants', [])
        
        # Format variants
        formatted_variants = []
        for variant in variants:
            try:
                price = variant.get('price', {})
                images = variant.get('images', [])
                variant_options = variant.get('variant_options', [])
                
                formatted_variants.append({
                    'id': variant['id'],
                    'name': variant['name'],
                    'sku': variant.get('sku'),
                    'ean': variant.get('ean'),
                    'variant_type': variant.get('variant_type'),
                    'variant_options': [{'name': opt.get('name'), 'value': opt.get('value')} for opt in variant_options],
                    'price': {
                        'value': price.get('value'),
                        'formatted': price.get('formatted'),
                        'currency': price.get('currency', {}).get('code') if price.get('currency') else None
                    } if price else None,
                    'stock_quantity': variant.get('stock_quantity'),
                    'available_quantity': variant.get('available_quantity'),
                    'image_url': images[0].get('url') if images else None,
                    'parent_product_id': variant.get('parent_product_id')
                })
            except Exception as e:
                logger.error(f"Error formatting variant {variant.get('id', 'unknown')}: {e}")
                continue
        
        return {
            'product_id': product_id,
            'variants': formatted_variants,
            'count': len(formatted_variants)
        }
    
    async def _get_product_availability(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Check product stock and availability status"""
        product_id = args['product_id']
        
        try:
            async with self.client as session:
                result = await session.execute(PRODUCT_AVAILABILITY_QUERY, variable_values={
                    'product_id': product_id
                })
        except Exception as e:
            logger.error(f"Error fetching availability for product {product_id}: {str(e)}")
            return {'error': f'Failed to fetch product availability: {str(e)}'}
        
        availability = result.get('getProductAvailability')
        if not availability:
            return {'error': f'Availability information for product {product_id} not found'}
        
        return {
            'product_id': availability['product_id'],
            'sku': availability.get('sku'),
            'name': availability.get('name'),
            'stock_quantity': availability.get('stock_quantity'),
            'available_quantity': availability.get('available_quantity'),
            'reserved_quantity': availability.get('reserved_quantity'),
            'availability_status': availability.get('availability_status'),
            'estimated_restock_date': availability.get('estimated_restock_date'),
            'supplier_stock': availability.get('supplier_stock'),
            'backorder_allowed': availability.get('backorder_allowed'),
            'min_order_quantity': availability.get('min_order_quantity'),
            'max_order_quantity': availability.get('max_order_quantity'),
            'location': availability.get('location'),
            'last_stock_update': availability.get('last_stock_update')
        }
    
    async def _get_related_products(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get related or recommended products"""
        product_id = args['product_id']
        relation_type = args.get('relation_type', 'related')
        
        try:
            async with self.client as session:
                result = await session.execute(RELATED_PRODUCTS_QUERY, variable_values={
                    'product_id': product_id,
                    'type': relation_type
                })
        except Exception as e:
            logger.error(f"Error fetching related products for {product_id}: {str(e)}")
            return {'error': f'Failed to fetch related products: {str(e)}'}
        
        related_products = result.get('getRelatedProducts', [])
        
        # Format related products
        formatted_products = []
        for product in related_products:
            try:
                category = product.get('category', {})
                price = product.get('price', {})
                images = product.get('images', [])
                
                formatted_products.append({
                    'id': product['id'],
                    'name': product['name'],
                    'sku': product.get('sku'),
                    'description': product.get('description'),
                    'category': category.get('name') if category else None,
                    'price': {
                        'value': price.get('value'),
                        'formatted': price.get('formatted'),
                        'currency': price.get('currency', {}).get('code') if price.get('currency') else None
                    } if price else None,
                    'stock_quantity': product.get('stock_quantity'),
                    'available_quantity': product.get('available_quantity'),
                    'image_url': images[0].get('url') if images else None,
                    'relation_type': product.get('relation_type'),
                    'relation_score': product.get('relation_score')
                })
            except Exception as e:
                logger.error(f"Error formatting related product {product.get('id', 'unknown')}: {e}")
                continue
        
        return {
            'product_id': product_id,
            'relation_type': relation_type,
            'related_products': formatted_products,
            'count': len(formatted_products)
        }
    
    async def _get_product_prices(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed pricing information for a product"""
        product_id = args['product_id']
        
        try:
            async with self.client as session:
                result = await session.execute(PRODUCT_PRICES_QUERY, variable_values={
                    'product_id': product_id
                })
        except Exception as e:
            logger.error(f"Error fetching prices for product {product_id}: {str(e)}")
            return {'error': f'Failed to fetch product prices: {str(e)}'}
        
        prices = result.get('getProductPrices')
        if not prices:
            return {'error': f'Pricing information for product {product_id} not found'}
        
        # Format pricing data
        base_price = prices.get('base_price', {})
        sale_price = prices.get('sale_price', {})
        discount_amount = prices.get('discount_amount', {})
        price_tiers = prices.get('price_tiers', [])
        promotional_price = prices.get('promotional_price', {})
        
        return {
            'product_id': prices['product_id'],
            'sku': prices.get('sku'),
            'name': prices.get('name'),
            'base_price': {
                'value': base_price.get('value'),
                'formatted': base_price.get('formatted'),
                'currency': base_price.get('currency', {}).get('code') if base_price.get('currency') else None
            } if base_price else None,
            'sale_price': {
                'value': sale_price.get('value'),
                'formatted': sale_price.get('formatted'),
                'currency': sale_price.get('currency', {}).get('code') if sale_price.get('currency') else None
            } if sale_price else None,
            'discount': {
                'amount': discount_amount.get('value'),
                'percentage': discount_amount.get('percentage')
            } if discount_amount else None,
            'price_tiers': [
                {
                    'min_quantity': tier.get('min_quantity'),
                    'price': tier.get('price', {}).get('formatted'),
                    'value': tier.get('price', {}).get('value')
                } for tier in price_tiers
            ],
            'tax_rate': prices.get('tax_rate'),
            'price_includes_tax': prices.get('price_includes_tax'),
            'valid_from': prices.get('valid_from'),
            'valid_to': prices.get('valid_to'),
            'promotional_price': {
                'value': promotional_price.get('value'),
                'formatted': promotional_price.get('formatted'),
                'valid_from': promotional_price.get('valid_from'),
                'valid_to': promotional_price.get('valid_to')
            } if promotional_price else None
        }
    
    async def _list_invoices(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List invoices with optional filtering"""
        variables = {}
        
        # InvoiceParams for pagination/sorting
        variables['params'] = {
            'limit': args.get('limit', 30),
            'order_by': 'issue_date',
            'sort': 'DESC'
        }
        
        # InvoiceFilter for filtering
        filter_params = {}
        
        # Add date filters
        if 'from_date' in args:
            filter_params['issue_date_from'] = args['from_date']
        if 'to_date' in args:
            filter_params['issue_date_to'] = args['to_date']
        if 'status' in args:
            filter_params['status'] = args['status']
            
        if filter_params:
            variables['filter'] = filter_params
        
        async with self.client as session:
            result = await session.execute(INVOICE_LIST_QUERY, variable_values=variables)
        
        invoices_data = result.get('getInvoiceList', {})
        invoices = invoices_data.get('data', [])
        page_info = invoices_data.get('pageInfo', {})
        
        # Format invoices for better readability
        formatted_invoices = []
        for invoice in invoices:
            try:
                customer = invoice.get('customer', {})
                customer_name = customer.get('company_name', '')
                if not customer_name:
                    customer_name = f"{customer.get('name', '')} {customer.get('surname', '')}".strip()
                
                # Safely get invoice sum and currency
                invoice_sum = invoice.get('sum', {})
                invoice_value = invoice_sum.get('value', 'N/A')
                currency_code = invoice_sum.get('currency', {}).get('code', '')
                
                formatted_invoices.append({
                    'id': invoice['id'],
                    'invoice_num': invoice['invoice_num'],
                    'issue_date': invoice['issue_date'],
                    'due_date': invoice.get('due_date'),
                    'vat_date': invoice.get('vat_date'),
                    'customer': customer_name,
                    'email': customer.get('email'),
                    'status': invoice.get('status'),
                    'total': f"{invoice_value} {currency_code}".strip()
                })
            except Exception as e:
                logger.error(f"Error formatting invoice {invoice.get('invoice_num', 'unknown')}: {e}")
                continue
        
        return {
            'invoices': formatted_invoices,
            'count': len(formatted_invoices),
            'has_more': page_info.get('hasNextPage', False),
            'total_pages': page_info.get('totalPages')
        }
    
    async def _get_invoice(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed invoice information"""
        invoice_id = args['invoice_id']
        
        async with self.client as session:
            result = await session.execute(INVOICE_DETAIL_QUERY, variable_values={'id': invoice_id})
        
        invoice = result.get('getInvoice')
        if not invoice:
            return {'error': f'Invoice {invoice_id} not found'}
        
        # Format customer info
        customer = invoice.get('customer', {})
        customer_info = {
            'name': customer.get('company_name', '') or f"{customer.get('name', '')} {customer.get('surname', '')}".strip(),
            'email': customer.get('email'),
            'phone': customer.get('phone'),
            'company_id': customer.get('company_id'),
            'vat_id': customer.get('vat_id')
        }
        
        # Format address
        invoice_addr = invoice.get('invoice_address', {})
        
        # Format items
        items = []
        for item in invoice.get('items', []):
            items.append({
                'name': item['item_label'],
                'quantity': item['quantity'],
                'price': item['price']['formatted'],
                'tax_rate': item.get('tax_rate')
            })
        
        return {
            'id': invoice['id'],
            'invoice_num': invoice['invoice_num'],
            'issue_date': invoice['issue_date'],
            'due_date': invoice.get('due_date'),
            'vat_date': invoice.get('vat_date'),
            'status': invoice.get('status'),
            'customer': customer_info,
            'invoice_address': {
                'street': invoice_addr.get('street'),
                'city': invoice_addr.get('city'),
                'zip': invoice_addr.get('zip'),
                'country': invoice_addr.get('country')
            },
            'items': items,
            'total': invoice['sum']['formatted'],
            'order_num': invoice.get('order', {}).get('order_num') if invoice.get('order') else None
        }
    
    async def _create_invoice(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new invoice from an order"""
        order_id = args['order_id']
        
        try:
            async with self.client as session:
                result = await session.execute(CREATE_INVOICE_MUTATION, variable_values={'order_id': order_id})
            
            created_invoice = result.get('createInvoice')
            if not created_invoice:
                return {'error': f'Failed to create invoice from order {order_id}'}
            
            return {
                'success': True,
                'invoice': {
                    'id': created_invoice['id'],
                    'invoice_num': created_invoice['invoice_num'],
                    'issue_date': created_invoice['issue_date'],
                    'due_date': created_invoice.get('due_date'),
                    'status': created_invoice.get('status'),
                    'total': created_invoice['sum']['formatted']
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating invoice from order {order_id}: {str(e)}")
            return {'error': f'Failed to create invoice: {str(e)}'}
    
    async def _get_proforma_invoice(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed proforma invoice information"""
        proforma_id = args['proforma_id']
        
        async with self.client as session:
            result = await session.execute(PROFORMA_INVOICE_QUERY, variable_values={'id': proforma_id})
        
        proforma = result.get('getProformaInvoice')
        if not proforma:
            return {'error': f'Proforma invoice {proforma_id} not found'}
        
        # Format customer info
        customer = proforma.get('customer', {})
        customer_info = {
            'name': customer.get('company_name', '') or f"{customer.get('name', '')} {customer.get('surname', '')}".strip(),
            'email': customer.get('email'),
            'phone': customer.get('phone'),
            'company_id': customer.get('company_id'),
            'vat_id': customer.get('vat_id')
        }
        
        # Format address
        invoice_addr = proforma.get('invoice_address', {})
        
        # Format items
        items = []
        for item in proforma.get('items', []):
            items.append({
                'name': item['item_label'],
                'quantity': item['quantity'],
                'price': item['price']['formatted'],
                'tax_rate': item.get('tax_rate')
            })
        
        return {
            'id': proforma['id'],
            'invoice_num': proforma['invoice_num'],
            'issue_date': proforma['issue_date'],
            'due_date': proforma.get('due_date'),
            'vat_date': proforma.get('vat_date'),
            'status': proforma.get('status'),
            'customer': customer_info,
            'invoice_address': {
                'street': invoice_addr.get('street'),
                'city': invoice_addr.get('city'),
                'zip': invoice_addr.get('zip'),
                'country': invoice_addr.get('country')
            },
            'items': items,
            'total': proforma['sum']['formatted'],
            'order_num': proforma.get('order', {}).get('order_num') if proforma.get('order') else None
        }
    
    async def _list_credit_notes(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List credit notes with optional filtering"""
        variables = {}
        
        # CreditNoteParams for pagination/sorting
        params = {
            'limit': args.get('limit', 30),
            'order_by': 'issue_date',
            'sort': 'DESC'
        }
        
        # Add date filters to params if provided (API might handle it differently)
        if 'from_date' in args:
            params['from_date'] = args['from_date']
        if 'to_date' in args:
            params['to_date'] = args['to_date']
            
        variables['params'] = params
        
        async with self.client as session:
            result = await session.execute(CREDIT_NOTE_LIST_QUERY, variable_values=variables)
        
        credit_notes_data = result.get('getCreditNoteList', {})
        credit_notes = credit_notes_data.get('data', [])
        page_info = credit_notes_data.get('pageInfo', {})
        
        # Apply client-side date filtering if needed
        if 'from_date' in args or 'to_date' in args:
            filtered_notes = []
            from_date_filter = None
            to_date_filter = None
            
            if 'from_date' in args:
                try:
                    from_date_filter = datetime.strptime(args['from_date'], '%Y-%m-%d')
                except ValueError:
                    logger.warning(f"Invalid from_date format: {args['from_date']}")
            
            if 'to_date' in args:
                try:
                    to_date_filter = datetime.strptime(args['to_date'], '%Y-%m-%d')
                except ValueError:
                    logger.warning(f"Invalid to_date format: {args['to_date']}")
            
            for note in credit_notes:
                try:
                    note_date_str = note['issue_date'].split('T')[0] if 'T' in note['issue_date'] else note['issue_date'].split(' ')[0]
                    note_date = datetime.strptime(note_date_str, '%Y-%m-%d')
                    
                    if from_date_filter and note_date < from_date_filter:
                        continue
                    if to_date_filter and note_date > to_date_filter:
                        continue
                    
                    filtered_notes.append(note)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Error parsing credit note date: {e}")
                    continue
            
            credit_notes = filtered_notes
        
        # Format credit notes for better readability
        formatted_notes = []
        for note in credit_notes:
            try:
                customer = note.get('customer', {})
                customer_name = customer.get('company_name', '')
                if not customer_name:
                    customer_name = f"{customer.get('name', '')} {customer.get('surname', '')}".strip()
                
                # Safely get credit note sum and currency
                note_sum = note.get('sum', {})
                note_value = note_sum.get('value', 'N/A')
                currency_code = note_sum.get('currency', {}).get('code', '')
                
                formatted_notes.append({
                    'id': note['id'],
                    'credit_note_num': note['credit_note_num'],
                    'issue_date': note['issue_date'],
                    'customer': customer_name,
                    'email': customer.get('email'),
                    'status': note.get('status'),
                    'total': f"{note_value} {currency_code}".strip()
                })
            except Exception as e:
                logger.error(f"Error formatting credit note {note.get('credit_note_num', 'unknown')}: {e}")
                continue
        
        return {
            'credit_notes': formatted_notes,
            'count': len(formatted_notes),
            'has_more': page_info.get('hasNextPage', False),
            'total_pages': page_info.get('totalPages')
        }
    
    async def _get_credit_note(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed credit note information"""
        credit_note_id = args['credit_note_id']
        
        async with self.client as session:
            result = await session.execute(CREDIT_NOTE_DETAIL_QUERY, variable_values={'id': credit_note_id})
        
        credit_note = result.get('getCreditNote')
        if not credit_note:
            return {'error': f'Credit note {credit_note_id} not found'}
        
        # Format customer info
        customer = credit_note.get('customer', {})
        customer_info = {
            'name': customer.get('company_name', '') or f"{customer.get('name', '')} {customer.get('surname', '')}".strip(),
            'email': customer.get('email'),
            'phone': customer.get('phone'),
            'company_id': customer.get('company_id'),
            'vat_id': customer.get('vat_id')
        }
        
        # Format address
        invoice_addr = credit_note.get('invoice_address', {})
        
        # Format items
        items = []
        for item in credit_note.get('items', []):
            items.append({
                'name': item['item_label'],
                'quantity': item['quantity'],
                'price': item['price']['formatted'],
                'tax_rate': item.get('tax_rate')
            })
        
        return {
            'id': credit_note['id'],
            'credit_note_num': credit_note['credit_note_num'],
            'issue_date': credit_note['issue_date'],
            'status': credit_note.get('status'),
            'customer': customer_info,
            'invoice_address': {
                'street': invoice_addr.get('street'),
                'city': invoice_addr.get('city'),
                'zip': invoice_addr.get('zip'),
                'country': invoice_addr.get('country')
            },
            'items': items,
            'total': credit_note['sum']['formatted'],
            'invoice_num': credit_note.get('invoice', {}).get('invoice_num') if credit_note.get('invoice') else None
        }
    
    async def _list_warehouse_items(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List warehouse items with optional filtering"""
        params = {
            'limit': args.get('limit', 30)
        }
        
        # Add filters if provided
        if 'category' in args:
            params['category'] = args['category']
        if 'search' in args:
            params['search'] = args['search']
        if 'low_stock' in args:
            params['low_stock'] = args['low_stock']
            
        variables = {'params': params}
        
        try:
            async with self.client as session:
                result = await session.execute(WAREHOUSE_ITEM_LIST_QUERY, variable_values=variables)
            
            warehouse_data = result.get('getWarehouseItemList', {})
            items = warehouse_data.get('data', [])
            page_info = warehouse_data.get('pageInfo', {})
            
            # Format items for better readability
            formatted_items = []
            for item in items:
                try:
                    category = item.get('category', {})
                    price = item.get('price', {})
                    
                    formatted_items.append({
                        'id': item['id'],
                        'name': item['name'],
                        'sku': item['sku'],
                        'ean': item.get('ean'),
                        'description': item.get('description'),
                        'category': category.get('name') if category else None,
                        'price': f"{price.get('value', 'N/A')} {price.get('currency', {}).get('code', '')}".strip(),
                        'stock_quantity': item.get('stock_quantity'),
                        'reserved_quantity': item.get('reserved_quantity'),
                        'available_quantity': item.get('available_quantity'),
                        'location': item.get('location'),
                        'last_updated': item.get('last_updated')
                    })
                except Exception as e:
                    logger.error(f"Error formatting warehouse item {item.get('id', 'unknown')}: {e}")
                    continue
            
            return {
                'items': formatted_items,
                'count': len(formatted_items),
                'has_more': page_info.get('hasNextPage', False),
                'total_pages': page_info.get('totalPages')
            }
            
        except Exception as e:
            logger.error(f"Error listing warehouse items: {str(e)}")
            return {'error': f'Failed to list warehouse items: {str(e)}'}
    
    async def _get_warehouse_item(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed warehouse item information"""
        item_id = args['id']
        
        try:
            async with self.client as session:
                result = await session.execute(WAREHOUSE_ITEM_DETAIL_QUERY, variable_values={'id': item_id})
            
            item = result.get('getWarehouseItem')
            if not item:
                return {'error': f'Warehouse item {item_id} not found'}
            
            # Format item details
            category = item.get('category', {})
            price = item.get('price', {})
            dimensions = item.get('dimensions', {})
            supplier = item.get('supplier', {})
            
            return {
                'id': item['id'],
                'name': item['name'],
                'sku': item['sku'],
                'ean': item.get('ean'),
                'description': item.get('description'),
                'category': {
                    'id': category.get('id'),
                    'name': category.get('name')
                } if category else None,
                'price': {
                    'value': price.get('value'),
                    'formatted': price.get('formatted'),
                    'currency': price.get('currency', {}).get('code')
                },
                'stock_quantity': item.get('stock_quantity'),
                'reserved_quantity': item.get('reserved_quantity'),
                'available_quantity': item.get('available_quantity'),
                'location': item.get('location'),
                'weight': item.get('weight'),
                'dimensions': {
                    'length': dimensions.get('length'),
                    'width': dimensions.get('width'),
                    'height': dimensions.get('height'),
                    'unit': dimensions.get('unit')
                } if dimensions else None,
                'supplier': {
                    'id': supplier.get('id'),
                    'name': supplier.get('name'),
                    'contact_email': supplier.get('contact_email')
                } if supplier else None,
                'last_updated': item.get('last_updated'),
                'created_at': item.get('created_at')
            }
            
        except Exception as e:
            logger.error(f"Error getting warehouse item {item_id}: {str(e)}")
            return {'error': f'Failed to get warehouse item: {str(e)}'}
    
    async def _get_stock_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get stock information for one or more products"""
        product_ids = args['product_ids']
        
        if not product_ids:
            return {'error': 'No product IDs provided'}
        
        try:
            async with self.client as session:
                result = await session.execute(STOCK_INFO_QUERY, variable_values={'product_ids': product_ids})
            
            stock_info = result.get('getStockInfo', [])
            
            # Format stock information
            formatted_stock = []
            for stock in stock_info:
                try:
                    last_movement = stock.get('last_stock_movement', {})
                    
                    formatted_stock.append({
                        'product_id': stock['product_id'],
                        'sku': stock['sku'],
                        'name': stock['name'],
                        'stock_quantity': stock.get('stock_quantity'),
                        'reserved_quantity': stock.get('reserved_quantity'),
                        'available_quantity': stock.get('available_quantity'),
                        'location': stock.get('location'),
                        'last_stock_movement': {
                            'date': last_movement.get('date'),
                            'type': last_movement.get('type'),
                            'quantity': last_movement.get('quantity'),
                            'reason': last_movement.get('reason')
                        } if last_movement else None,
                        'reorder_level': stock.get('reorder_level'),
                        'reorder_quantity': stock.get('reorder_quantity')
                    })
                except Exception as e:
                    logger.error(f"Error formatting stock info for product {stock.get('product_id', 'unknown')}: {e}")
                    continue
            
            return {
                'stock_info': formatted_stock,
                'count': len(formatted_stock)
            }
            
        except Exception as e:
            logger.error(f"Error getting stock info: {str(e)}")
            return {'error': f'Failed to get stock info: {str(e)}'}
    
    async def _update_warehouse_item(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Update warehouse item information (mutation)"""
        item_id = args['id']
        
        # Build input object from provided arguments
        input_data = {'id': item_id}
        
        # Add optional fields if provided
        if 'name' in args:
            input_data['name'] = args['name']
        if 'stock_quantity' in args:
            input_data['stock_quantity'] = args['stock_quantity']
        if 'location' in args:
            input_data['location'] = args['location']
        if 'price' in args:
            input_data['price'] = args['price']
        
        # Validate that we have at least one field to update
        if len(input_data) == 1:  # Only ID was provided
            return {'error': 'No fields provided to update'}
        
        try:
            async with self.client as session:
                result = await session.execute(UPDATE_WAREHOUSE_ITEM_MUTATION, variable_values={'input': input_data})
            
            updated_item = result.get('updateWarehouseItem')
            if not updated_item:
                return {'error': f'Failed to update warehouse item {item_id}'}
            
            return {
                'success': True,
                'updated_item': {
                    'id': updated_item['id'],
                    'name': updated_item['name'],
                    'sku': updated_item['sku'],
                    'stock_quantity': updated_item.get('stock_quantity'),
                    'available_quantity': updated_item.get('available_quantity'),
                    'location': updated_item.get('location'),
                    'last_updated': updated_item.get('last_updated')
                }
            }
            
        except Exception as e:
            logger.error(f"Error updating warehouse item {item_id}: {str(e)}")
            return {'error': f'Failed to update warehouse item: {str(e)}'}
    
    async def _list_customers(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List customers with optional search and filtering"""
        variables = {}
        
        # CustomerParams for pagination/sorting
        params = {
            'limit': args.get('limit', 30),
            'order_by': args.get('sort_by', 'name'),
            'sort': args.get('sort_order', 'ASC')
        }
        variables['params'] = params
        
        # CustomerFilter for filtering
        filter_params = {}
        
        if 'search' in args and args['search']:
            filter_params['search'] = args['search']
        
        if 'customer_type' in args and args['customer_type']:
            filter_params['customer_type'] = args['customer_type']
            
        if 'status' in args and args['status']:
            filter_params['status'] = args['status']
        
        if filter_params:
            variables['filter'] = filter_params
        
        try:
            async with self.client as session:
                result = await session.execute(CUSTOMER_LIST_QUERY, variable_values=variables)
        except Exception as e:
            logger.error(f"Error executing customer list query: {str(e)}")
            return {'error': f'Failed to fetch customers: {str(e)}'}
        
        customers_data = result.get('getCustomerList', {})
        customers = customers_data.get('data', [])
        page_info = customers_data.get('pageInfo', {})
        
        # Format customers for better readability
        formatted_customers = []
        for customer in customers:
            try:
                # Determine customer name
                customer_name = customer.get('company_name', '')
                if not customer_name:
                    customer_name = f"{customer.get('name', '')} {customer.get('surname', '')}".strip()
                
                # Safely get total spent and currency
                total_spent = customer.get('total_spent', {})
                spent_value = total_spent.get('value', 0)
                currency_code = total_spent.get('currency', {}).get('code', '')
                
                # Format address
                address = customer.get('address', {})
                formatted_address = None
                if address:
                    formatted_address = f"{address.get('street', '')}, {address.get('city', '')} {address.get('zip', '')}, {address.get('country', '')}".strip(' ,')
                
                formatted_customers.append({
                    'id': customer['id'],
                    'name': customer_name,
                    'email': customer.get('email'),
                    'phone': customer.get('phone'),
                    'customer_type': customer.get('customer_type'),
                    'status': customer.get('status'),
                    'company_id': customer.get('company_id'),
                    'vat_id': customer.get('vat_id'),
                    'registration_date': customer.get('registration_date'),
                    'last_order_date': customer.get('last_order_date'),
                    'total_orders': customer.get('total_orders', 0),
                    'total_spent': f"{spent_value} {currency_code}".strip() if spent_value else "0",
                    'address': formatted_address
                })
            except Exception as e:
                logger.error(f"Error formatting customer {customer.get('id', 'unknown')}: {e}")
                continue
        
        return {
            'customers': formatted_customers,
            'count': len(formatted_customers),
            'has_more': page_info.get('hasNextPage', False),
            'total_pages': page_info.get('totalPages'),
            'search_query': args.get('search'),
            'filters': {
                'customer_type': args.get('customer_type'),
                'status': args.get('status')
            }
        }
    
    async def _get_customer(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed customer information"""
        customer_id = args['customer_id']
        
        try:
            async with self.client as session:
                result = await session.execute(CUSTOMER_DETAIL_QUERY, variable_values={'id': customer_id})
        except Exception as e:
            logger.error(f"Error executing customer detail query: {str(e)}")
            return {'error': f'Failed to fetch customer details: {str(e)}'}
        
        customer = result.get('getCustomer')
        if not customer:
            return {'error': f'Customer {customer_id} not found'}
        
        try:
            # Determine customer name
            customer_name = customer.get('company_name', '')
            if not customer_name:
                customer_name = f"{customer.get('name', '')} {customer.get('surname', '')}".strip()
            
            # Format addresses
            address = customer.get('address', {})
            delivery_address = customer.get('delivery_address', {})
            
            formatted_address = None
            if address:
                formatted_address = {
                    'street': address.get('street'),
                    'city': address.get('city'),
                    'zip': address.get('zip'),
                    'country': address.get('country')
                }
            
            formatted_delivery_address = None
            if delivery_address:
                formatted_delivery_address = {
                    'street': delivery_address.get('street'),
                    'city': delivery_address.get('city'),
                    'zip': delivery_address.get('zip'),
                    'country': delivery_address.get('country')
                }
            
            # Format total spent
            total_spent = customer.get('total_spent', {})
            spent_formatted = total_spent.get('formatted', '0')
            
            # Format preferences
            preferences = customer.get('preferences', {})
            
            # Format recent orders
            recent_orders = []
            for order in customer.get('recent_orders', []):
                recent_orders.append({
                    'id': order['id'],
                    'order_num': order['order_num'],
                    'date': order['pur_date'],
                    'status': order.get('status', {}).get('name'),
                    'total': order.get('sum', {}).get('formatted', '0')
                })
            
            return {
                'id': customer['id'],
                'name': customer_name,
                'email': customer.get('email'),
                'phone': customer.get('phone'),
                'customer_type': customer.get('customer_type'),
                'status': customer.get('status'),
                'company_id': customer.get('company_id'),
                'vat_id': customer.get('vat_id'),
                'registration_date': customer.get('registration_date'),
                'last_order_date': customer.get('last_order_date'),
                'last_login_date': customer.get('last_login_date'),
                'total_orders': customer.get('total_orders', 0),
                'total_spent': spent_formatted,
                'address': formatted_address,
                'delivery_address': formatted_delivery_address,
                'preferences': {
                    'newsletter_subscription': preferences.get('newsletter_subscription'),
                    'marketing_emails': preferences.get('marketing_emails'),
                    'language': preferences.get('language')
                },
                'notes': customer.get('notes'),
                'recent_orders': recent_orders
            }
            
        except Exception as e:
            logger.error(f"Error formatting customer {customer_id}: {str(e)}")
            return {'error': f'Error processing customer data: {str(e)}'}
    
    async def _get_categories(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get product category tree with hierarchical structure"""
        variables = {}
        
        # CategoryParams for filtering and configuration
        params = {}
        
        if 'parent_id' in args and args['parent_id']:
            params['parent_id'] = args['parent_id']
        
        if 'max_depth' in args:
            params['max_depth'] = args['max_depth']
        else:
            params['max_depth'] = 3  # Default depth
        
        if 'include_inactive' in args:
            params['include_inactive'] = args['include_inactive']
        else:
            params['include_inactive'] = False
        
        if 'include_empty' in args:
            params['include_empty'] = args['include_empty']
        else:
            params['include_empty'] = False
        
        if params:
            variables['params'] = params
        
        try:
            async with self.client as session:
                result = await session.execute(CATEGORY_TREE_QUERY, variable_values=variables)
        except Exception as e:
            logger.error(f"Error executing category tree query: {str(e)}")
            return {'error': f'Failed to fetch categories: {str(e)}'}
        
        categories = result.get('getCategoryTree', [])
        
        def format_category(category):
            """Recursively format category with its children"""
            try:
                formatted = {
                    'id': category['id'],
                    'name': category['name'],
                    'slug': category.get('slug'),
                    'description': category.get('description'),
                    'parent_id': category.get('parent_id'),
                    'level': category.get('level', 0),
                    'position': category.get('position', 0),
                    'is_active': category.get('is_active', True),
                    'product_count': category.get('product_count', 0),
                    'image_url': category.get('image_url'),
                    'seo_title': category.get('seo_title'),
                    'seo_description': category.get('seo_description'),
                    'created_at': category.get('created_at'),
                    'updated_at': category.get('updated_at')
                }
                
                # Recursively format children
                children = category.get('children', [])
                if children:
                    formatted['children'] = []
                    for child in children:
                        formatted_child = format_category(child)
                        if formatted_child:
                            formatted['children'].append(formatted_child)
                
                return formatted
                
            except Exception as e:
                logger.error(f"Error formatting category {category.get('id', 'unknown')}: {e}")
                return None
        
        # Format all root categories
        formatted_categories = []
        total_categories = 0
        active_categories = 0
        
        for category in categories:
            formatted_category = format_category(category)
            if formatted_category:
                formatted_categories.append(formatted_category)
                # Count categories recursively
                def count_categories(cat):
                    count = 1
                    active_count = 1 if cat.get('is_active', True) else 0
                    for child in cat.get('children', []):
                        child_count, child_active_count = count_categories(child)
                        count += child_count
                        active_count += child_active_count
                    return count, active_count
                
                cat_count, cat_active_count = count_categories(formatted_category)
                total_categories += cat_count
                active_categories += cat_active_count
        
        return {
            'categories': formatted_categories,
            'total_categories': total_categories,
            'active_categories': active_categories,
            'max_depth': args.get('max_depth', 3),
            'filters': {
                'parent_id': args.get('parent_id'),
                'include_inactive': args.get('include_inactive', False),
                'include_empty': args.get('include_empty', False)
            }
        }
    
    # Configuration & Lookup Tools Methods
    async def _get_order_statuses(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get list of order statuses"""
        try:
            async with self.client as session:
                result = await session.execute(ORDER_STATUSES_QUERY)
            
            statuses = result.get('getOrderStatuses', [])
            
            # Format statuses for better readability
            formatted_statuses = []
            for status in statuses:
                formatted_statuses.append({
                    'id': status['id'],
                    'name': status['name'],
                    'description': status.get('description'),
                    'color': status.get('color'),
                    'is_active': status.get('is_active', True),
                    'sort_order': status.get('sort_order')
                })
            
            return {
                'statuses': formatted_statuses,
                'count': len(formatted_statuses)
            }
            
        except Exception as e:
            logger.error(f"Error fetching order statuses: {str(e)}")
            return {'error': f'Failed to fetch order statuses: {str(e)}'}
    
    async def _get_payment_methods(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get available payment methods"""
        try:
            async with self.client as session:
                result = await session.execute(PAYMENT_METHODS_QUERY)
            
            methods = result.get('getPaymentMethods', [])
            
            # Format payment methods for better readability
            formatted_methods = []
            for method in methods:
                formatted_methods.append({
                    'id': method['id'],
                    'name': method['name'],
                    'description': method.get('description'),
                    'is_active': method.get('is_active', True),
                    'sort_order': method.get('sort_order'),
                    'settings': method.get('settings', [])
                })
            
            return {
                'payment_methods': formatted_methods,
                'count': len(formatted_methods)
            }
            
        except Exception as e:
            logger.error(f"Error fetching payment methods: {str(e)}")
            return {'error': f'Failed to fetch payment methods: {str(e)}'}
    
    async def _get_delivery_methods(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get available delivery methods"""
        try:
            async with self.client as session:
                result = await session.execute(DELIVERY_METHODS_QUERY)
            
            methods = result.get('getDeliveryMethods', [])
            
            # Format delivery methods for better readability
            formatted_methods = []
            for method in methods:
                price_info = method.get('price', {})
                price_value = price_info.get('value', 0)
                currency_code = price_info.get('currency', {}).get('code', '')
                
                formatted_methods.append({
                    'id': method['id'],
                    'name': method['name'],
                    'description': method.get('description'),
                    'price': f"{price_value} {currency_code}".strip() if price_value else "Free",
                    'is_active': method.get('is_active', True),
                    'sort_order': method.get('sort_order'),
                    'settings': method.get('settings', [])
                })
            
            return {
                'delivery_methods': formatted_methods,
                'count': len(formatted_methods)
            }
            
        except Exception as e:
            logger.error(f"Error fetching delivery methods: {str(e)}")
            return {'error': f'Failed to fetch delivery methods: {str(e)}'}
    
    async def _get_countries(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get list of countries"""
        try:
            async with self.client as session:
                result = await session.execute(COUNTRIES_QUERY)
            
            countries = result.get('getCountries', [])
            
            # Format countries for better readability
            formatted_countries = []
            for country in countries:
                formatted_countries.append({
                    'id': country['id'],
                    'name': country['name'],
                    'code': country['code'],
                    'iso_code': country.get('iso_code'),
                    'is_active': country.get('is_active', True),
                    'sort_order': country.get('sort_order')
                })
            
            return {
                'countries': formatted_countries,
                'count': len(formatted_countries)
            }
            
        except Exception as e:
            logger.error(f"Error fetching countries: {str(e)}")
            return {'error': f'Failed to fetch countries: {str(e)}'}
    
    async def _get_currencies(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get list of currencies"""
        try:
            async with self.client as session:
                result = await session.execute(CURRENCIES_QUERY)
            
            currencies = result.get('getCurrencies', [])
            
            # Format currencies for better readability
            formatted_currencies = []
            for currency in currencies:
                formatted_currencies.append({
                    'id': currency['id'],
                    'name': currency['name'],
                    'code': currency['code'],
                    'symbol': currency['symbol'],
                    'exchange_rate': currency.get('exchange_rate'),
                    'is_default': currency.get('is_default', False),
                    'is_active': currency.get('is_active', True)
                })
            
            return {
                'currencies': formatted_currencies,
                'count': len(formatted_currencies)
            }
            
        except Exception as e:
            logger.error(f"Error fetching currencies: {str(e)}")
            return {'error': f'Failed to fetch currencies: {str(e)}'}
    
    async def _update_order_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Update order status (mutation)"""
        order_id = args['order_id']
        status_id = args['status_id']
        
        try:
            async with self.client as session:
                result = await session.execute(
                    UPDATE_ORDER_STATUS_MUTATION,
                    variable_values={
                        'order_id': order_id,
                        'status_id': status_id
                    }
                )
            
            updated_order = result.get('updateOrderStatus')
            if not updated_order:
                return {'error': f'Failed to update order {order_id} status'}
            
            return {
                'success': True,
                'order': {
                    'id': updated_order['id'],
                    'order_num': updated_order['order_num'],
                    'status': {
                        'id': updated_order['status']['id'],
                        'name': updated_order['status']['name']
                    },
                    'last_change': updated_order['last_change']
                }
            }
            
        except Exception as e:
            logger.error(f"Error updating order {order_id} status: {str(e)}")
            return {'error': f'Failed to update order status: {str(e)}'}
    
    async def _create_product_package(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create product package (mutation)"""
        try:
            # Build the input object
            package_input = {
                'name': args['name'],
                'products': args['products'],
                'price': args['price'],
                'currency_code': args.get('currency_code', 'EUR'),
                'is_active': args.get('is_active', True)
            }
            
            # Add optional description
            if 'description' in args:
                package_input['description'] = args['description']
            
            async with self.client as session:
                result = await session.execute(
                    CREATE_PRODUCT_PACKAGE_MUTATION,
                    variable_values={'input': package_input}
                )
            
            created_package = result.get('createProductPackage')
            if not created_package:
                return {'error': 'Failed to create product package'}
            
            # Format the response
            price_info = created_package.get('price', {})
            price_value = price_info.get('value', 0)
            currency_code = price_info.get('currency', {}).get('code', '')
            
            return {
                'success': True,
                'package': {
                    'id': created_package['id'],
                    'name': created_package['name'],
                    'description': created_package.get('description'),
                    'products': created_package.get('products', []),
                    'price': f"{price_value} {currency_code}".strip(),
                    'is_active': created_package.get('is_active', True),
                    'created_at': created_package.get('created_at')
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating product package: {str(e)}")
            return {'error': f'Failed to create product package: {str(e)}'}
    
    async def _update_product_availability(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Update product availability (mutation)"""
        product_id = args['product_id']
        
        try:
            # Build the availability input object
            availability_input = {}
            
            if 'is_available' in args:
                availability_input['is_available'] = args['is_available']
            if 'stock_quantity' in args:
                availability_input['stock_quantity'] = args['stock_quantity']
            if 'availability_text' in args:
                availability_input['availability_text'] = args['availability_text']
            if 'delivery_date' in args:
                availability_input['delivery_date'] = args['delivery_date']
            
            async with self.client as session:
                result = await session.execute(
                    UPDATE_PRODUCT_AVAILABILITY_MUTATION,
                    variable_values={
                        'product_id': product_id,
                        'availability': availability_input
                    }
                )
            
            updated_availability = result.get('updateProductAvailability')
            if not updated_availability:
                return {'error': f'Failed to update product {product_id} availability'}
            
            return {
                'success': True,
                'availability': {
                    'product_id': updated_availability['product_id'],
                    'is_available': updated_availability.get('is_available'),
                    'stock_quantity': updated_availability.get('stock_quantity'),
                    'available_quantity': updated_availability.get('available_quantity'),
                    'availability_text': updated_availability.get('availability_text'),
                    'delivery_date': updated_availability.get('delivery_date'),
                    'last_updated': updated_availability.get('last_updated')
                }
            }
            
        except Exception as e:
            logger.error(f"Error updating product {product_id} availability: {str(e)}")
            return {'error': f'Failed to update product availability: {str(e)}'}
    
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
    server = BiznisWebMCPServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()