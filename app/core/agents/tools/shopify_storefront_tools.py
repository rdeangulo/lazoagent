"""
Lazo Agent — Shopify Storefront Tools

Agent tools that query the public Storefront MCP for product discovery,
product details, and shop policies/FAQs.
"""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool


@tool
async def search_products(query: str, limit: int = 3) -> str:
    """Search the store's product catalog by natural-language query.

    Use this when the customer asks about products, prices, availability,
    sizes, colors, or wants to know what LAZO sells. Returns the top
    matching products with live prices, variants, and availability from
    the Shopify store.

    Args:
        query: What the customer is looking for (e.g. "cinturón trenzado",
            "belt for jeans", "regalo para hombre").
        limit: Maximum number of products to return.
    """
    from app.services.shopify_storefront_service import shopify_storefront_service

    if not shopify_storefront_service.is_configured:
        return "Product catalog is not configured right now."

    products = await shopify_storefront_service.search_catalog(query)
    if not products:
        return f"No products found matching '{query}'."

    lines = []
    for p in products[:limit]:
        title = p.get("title") or "Unnamed product"
        url = p.get("url") or ""
        price = p.get("price_min") or "?"
        if p.get("price_max") and p["price_max"] != p.get("price_min"):
            price = f"{p['price_min']} – {p['price_max']}"

        avail = [v for v in p.get("variants") or [] if v.get("available")]
        unavail = [v for v in p.get("variants") or [] if v.get("available") is False]
        stock_summary = ""
        if avail or unavail:
            stock_summary = (
                f" | Disponible: {', '.join(v['title'] for v in avail) or 'ninguna variante'}"
            )
            if unavail:
                stock_summary += (
                    f" | Agotado: {', '.join(v['title'] for v in unavail)}"
                )

        lines.append(f"- {title} [{p.get('id')}] — {price}{stock_summary}\n  {url}")

    return "\n".join(lines)


@tool
async def get_product_details(
    product_id: str,
    size: Optional[str] = None,
    color: Optional[str] = None,
) -> str:
    """Get detailed information about a specific product by Shopify ID.

    Use this after `search_products` when you need more detail on a
    specific product — description, full sizes list, selected variant
    price and availability. Pass `size` and/or `color` to check a
    specific variant.

    Args:
        product_id: Shopify product gid (e.g. "gid://shopify/Product/9029685772527").
            Obtained from the `id` field returned by `search_products`.
        size: Optional — talla (e.g. "M (30-32)").
        color: Optional — color (e.g. "Negro").
    """
    from app.services.shopify_storefront_service import shopify_storefront_service

    if not shopify_storefront_service.is_configured:
        return "Product catalog is not configured right now."

    options: dict[str, str] = {}
    if size:
        options["Talla"] = size
    if color:
        options["Color"] = color

    product = await shopify_storefront_service.get_product_details(
        product_id, options=options or None
    )
    if not product:
        return f"Product {product_id} not found."

    lines = [f"{product.get('title') or 'Product'}"]
    if product.get("description"):
        lines.append(product["description"])

    if product.get("price_min"):
        price = product["price_min"]
        if product.get("price_max") and product["price_max"] != product["price_min"]:
            price = f"{product['price_min']} – {product['price_max']}"
        lines.append(f"Precio: {price}")

    for o in product.get("options") or []:
        vals = ", ".join(o.get("values") or [])
        if vals:
            lines.append(f"{o['name']}: {vals}")

    sv = product.get("selected_variant")
    if sv:
        status = "disponible" if sv.get("available") else "agotado"
        lines.append(f"Variante seleccionada: {sv.get('title')} — {sv.get('price')} ({status})")

    if product.get("url"):
        lines.append(f"Ver producto: {product['url']}")

    return "\n".join(lines)


@tool
async def search_policies(query: str) -> str:
    """Search the shop's policies & FAQs (shipping, returns, exchanges, etc.).

    Use this for questions about shipping times, countries shipped to,
    return/exchange policy, warranty, payment methods, and anything
    merchants typically publish as policies or FAQs.

    Tip: if the first query returns nothing, try English keywords
    ("shipping", "return", "refund") — the policy index is currently
    most reliable in English.

    Args:
        query: What the customer wants to know about the shop's policies.
    """
    from app.services.shopify_storefront_service import shopify_storefront_service

    if not shopify_storefront_service.is_configured:
        return "Policies are not available right now."

    items = await shopify_storefront_service.search_policies(query)
    if not items:
        return f"No policy or FAQ found matching '{query}'."

    return "\n\n".join(
        f"Q: {item['question']}\nA: {item['answer']}" for item in items
    )
