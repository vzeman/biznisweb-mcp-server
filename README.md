# BizniWeb MCP Server

A Model Context Protocol (MCP) server that enables LLMs to interact with BizniWeb e-shop through GraphQL API. This server allows AI assistants like Claude to access your BizniWeb data directly through conversational interfaces.
We develop MCP servers for various platforms. If you need a custom MCP server for your business, check out our services at [FlowHunt](https://www.flowhunt.io/services/mcp-server-development/).

## What is MCP?

The Model Context Protocol (MCP) is an open protocol that enables seamless integration between AI assistants and external data sources. With this MCP server, you can:

- Query your BizniWeb orders directly from Claude Desktop or other MCP-compatible AI tools
- Get real-time statistics and insights about your e-commerce data
- Search for specific orders or customers without leaving your AI conversation
- Analyze sales trends and order patterns through natural language

## Features

The server provides the following tools:

### 1. `list_orders`
List orders with optional date filtering
- **Parameters:**
  - `from_date` (optional): From date in YYYY-MM-DD format
  - `to_date` (optional): To date in YYYY-MM-DD format
  - `status` (optional): Order status ID
  - `limit` (optional): Maximum number of orders to return (default: 30)

### 2. `get_order`
Get detailed information about a specific order
- **Parameters:**
  - `order_num` (required): Order number

### 3. `order_statistics`
Get order statistics for a date range (automatically excludes cancelled and pending payment orders)
- **Parameters:**
  - `from_date` (optional): From date in YYYY-MM-DD format
  - `to_date` (optional): To date in YYYY-MM-DD format

### 4. `search_orders`
Search orders by customer name, email, or order number
- **Parameters:**
  - `query` (required): Search query

## Prerequisites

- Python 3.8 or higher
- BizniWeb API token (get it from Settings → BiznisWeb API in your BizniWeb account)
- Claude Desktop app (for Claude integration) or any MCP-compatible client

## Installation

1. Clone the repository:
```bash
git clone https://github.com/vzeman/biznisweb-mcp-server.git
cd biznisweb-mcp-server
```

2. Create a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
```

4. Configure API credentials:
```bash
cp .env.example .env
# Edit .env and add your BizniWeb API token
```

The `.env` file should contain:
```
BIZNISWEB_API_TOKEN=your_api_token_here
BIZNISWEB_API_URL=https://[youraccount].flox.sk/api/graphql
```

## Usage

### Quick Start with Claude Desktop

1. **Find your Claude Desktop configuration file:**
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - Linux: `~/.config/Claude/claude_desktop_config.json`

2. **Add the BizniWeb MCP server configuration:**

```json
{
  "mcpServers": {
    "biznisweb": {
      "command": "python",
      "args": ["-m", "biznisweb_mcp"],
      "cwd": "/Users/viktorzeman/work/biznisweb-mcp-server",
      "env": {
        "BIZNISWEB_API_TOKEN": "your_token_here",
        "BIZNISWEB_API_URL": "https://vevo.flox.sk/api/graphql"
      }
    }
  }
}
```

   **Important:** Replace `/Users/viktorzeman/work/biznisweb-mcp-server` with the actual path where you cloned this repository.

3. **Restart Claude Desktop**
   - Quit Claude Desktop completely
   - Start it again
   - You should see the hammer icon (🔨) in the text input area, indicating MCP servers are connected

4. **Verify the connection:**
   - In a new conversation, you should see "biznisweb" listed when MCP servers are active
   - Try asking: "Use the list_orders tool to show me orders from the last 7 days"

### Alternative Configuration Methods

#### Using .env file (Recommended for security)

Instead of putting your API token directly in the config, you can use the `.env` file:

```json
{
  "mcpServers": {
    "biznisweb": {
      "command": "python",
      "args": ["-m", "biznisweb_mcp"],
      "cwd": "/path/to/biznisweb-mcp-server"
    }
  }
}
```

Make sure your `.env` file in the server directory contains:
```
BIZNISWEB_API_TOKEN=your_token_here
BIZNISWEB_API_URL=https://www.vevo.sk/api/graphql
```

#### Using with UV (Fast Python package installer)

If you have `uv` installed:

```json
{
  "mcpServers": {
    "biznisweb": {
      "command": "uv",
      "args": ["run", "biznisweb-mcp"],
      "cwd": "/path/to/biznisweb-mcp-server"
    }
  }
}
```

### Testing the Server Standalone

You can test the server without Claude:

```bash
cd /path/to/biznisweb-mcp-server
source venv/bin/activate
python test_server.py
```

### With Other MCP Clients

Run the server:
```bash
python -m biznisweb_mcp
```

The server communicates via stdin/stdout using the MCP protocol.

## Example Usage in Claude

Once configured, you can interact with your BizniWeb data naturally:

### Basic Examples

```
"Show me orders from the last 7 days"
→ Claude will use the list_orders tool automatically

"Get details for order 2502001234"
→ Claude will use the get_order tool to fetch complete order information

"What were my sales statistics for July 2025?"
→ Claude will use the order_statistics tool with appropriate date ranges

"Find all orders from customer John Doe"
→ Claude will use the search_orders tool
```

### Advanced Examples

```
"Show me today's orders and calculate the total revenue"
→ Claude will list orders and perform calculations

"Which products sold the most this week?"
→ Claude will analyze order data and summarize product sales

"Are there any pending orders that need attention?"
→ Claude will check order statuses and highlight important ones

"Compare sales between last week and this week"
→ Claude will fetch statistics for both periods and create a comparison
```

### Direct Tool Usage

You can also explicitly request specific tools:

```
Use the list_orders tool to show me orders from 2025-07-01 to 2025-07-31

Use the get_order tool to get details for order 2502001234

Use the order_statistics tool to show me sales statistics for this month

Use the search_orders tool to find orders from customer "John Doe"
```

## Environment Variables

- `BIZNISWEB_API_TOKEN`: Your BizniWeb API token (required)
- `BIZNISWEB_API_URL`: API endpoint URL (default: https://vevo.flox.sk/api/graphql)

## Getting Your API Token

1. Log in to your BizniWeb account
2. Navigate to: **Settings → BiznisWeb API**
3. Click the **"New API Token"** button
4. Copy the generated token
5. Add it to your `.env` file or Claude configuration

### API Token Setup in BizniWeb

![BizniWeb API Token Setup](docs/biznisweb-api-token-setup.png)

The screenshot above shows where to find and configure your API token in the BizniWeb admin panel:
- Access the **BiznisWeb API** section from the Settings menu
- Your API token will be displayed in the token field
- The token format is: `b93jWTLi8SNmO1SaZYWOPsK8S5z7WTzN`
- You can see API usage statistics below the token

## Troubleshooting

### Common Issues

1. **"BizniWeb tools not available in Claude"**
   - Make sure you restarted Claude Desktop after adding the configuration
   - Check that the `cwd` path in the config points to the correct directory
   - Verify the hammer icon (🔨) appears in Claude's input field

2. **"API token not found" error**
   - Ensure your `.env` file exists in the server directory
   - Check that the token is correctly formatted (no extra spaces)
   - Verify the token hasn't expired in BizniWeb

3. **"Module not found" errors**
   - Make sure you're in the virtual environment: `source venv/bin/activate`
   - Reinstall dependencies: `pip install -e .`

4. **Connection errors**
   - Check your internet connection
   - Verify the API URL is correct (should be https://vevo.flox.sk/api/graphql)
   - Ensure your BizniWeb account has API access enabled

### Debug Mode

To see detailed logs, you can run the test script:

```bash
cd /path/to/biznisweb-mcp-server
source venv/bin/activate
python test_server.py
```

## Development

### Running in Development Mode

```bash
python biznisweb_mcp/server.py
```

### Project Structure

```
biznisweb-mcp-server/
├── biznisweb_mcp/
│   ├── __init__.py
│   └── server.py          # Main MCP server implementation
├── .env                   # Your API credentials (not in git)
├── .env.example          # Template for environment variables
├── pyproject.toml        # Project configuration
├── test_server.py        # Test script for debugging
└── README.md            # This file
```

### Adding New Tools

To add new tools to the server:

1. Add the tool definition in the `list_tools()` method
2. Implement the tool handler in the `call_tool()` method
3. Create the corresponding GraphQL query
4. Add the implementation method (e.g., `_your_new_tool()`)

## Data Filtering

The server automatically filters out orders with the following statuses:
- Storno (Cancelled)
- Platba online - platnosť vypršala (Online payment expired)
- Platba online - platba zamietnutá (Online payment rejected)
- Čaká na úhradu (Waiting for payment)
- GoPay - platebni metoda potvrzena (GoPay payment method confirmed)

This ensures that statistics and reports only include valid, completed orders.

## Security Considerations

- Never commit your `.env` file to version control
- Use environment variables or `.env` files for API tokens
- The server only has read access to your BizniWeb data
- All communication happens locally between Claude and the MCP server

## License

This project is licensed under the MIT License.

## Support

For issues or questions:
- Contact the MCP server developers: https://www.flowhunt.io/contact
- We can develop your own MCP server, read more: https://www.flowhunt.io/services/mcp-server-development/
- Create an issue on GitHub: https://github.com/vzeman/biznisweb-mcp-server/issues
- Check the MCP documentation: https://modelcontextprotocol.io/