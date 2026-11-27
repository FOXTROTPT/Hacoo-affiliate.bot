"""Telegram assistant that turns a product page into a ready-to-edit post."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import re
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
logger = logging.getLogger("hacoo_affiliate_bot")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
MAX_PAGE_BYTES = 3_000_000
MAX_IMAGE_BYTES = 8_000_000
TIMEOUT_SECONDS = 15
USER_AGENT = "HacooAffiliateBot/1.0 (+product-page metadata preview)"
DEFAULT_TAGS = "#Hacoo #Moda #Acessorios #Achados"


@dataclass
class Product:
    title: str
    description: str
    price: str
    image_url: str
    page_url: str


def _public_http_url(url: str) -> bool:
    """Allow public HTTP(S) hosts only, to reduce SSRF risk on hosted deployments."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        if parsed.username or parsed.password:
            return False
        host = parsed.hostname.rstrip(".").lower()
        if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
            return False
        for result in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80)):
            address = ipaddress.ip_address(result[4][0])
            if not address.is_global:
                return False
        return True
    except (ValueError, OSError):
        return False


def _fetch(url: str, *, max_bytes: int) -> tuple[bytes, str, str]:
    """Fetch a page or image with redirect, timeout, and response-size limits."""
    current = url
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
    with requests.Session() as session:
        for _ in range(6):
            if not _public_http_url(current):
                raise ValueError("O endereço não é público ou não é válido.")
            response = session.get(
                current,
                headers=headers,
                timeout=TIMEOUT_SECONDS,
                stream=True,
                allow_redirects=False,
            )
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("Location")
                response.close()
                if not location:
                    raise ValueError("A página redirecionou sem indicar o destino.")
                current = urljoin(current, location)
                continue
            response.raise_for_status()
            declared_size = response.headers.get("Content-Length")
            if declared_size and int(declared_size) > max_bytes:
                response.close()
                raise ValueError("O ficheiro é demasiado grande para processar.")
            content = bytearray()
            for chunk in response.iter_content(chunk_size=64 * 1024):
                content.extend(chunk)
                if len(content) > max_bytes:
                    response.close()
                    raise ValueError("O ficheiro é demasiado grande para processar.")
            content_type = response.headers.get("Content-Type", "")
            final_url = response.url
            response.close()
            return bytes(content), content_type, final_url
    raise ValueError("A página tem demasiados redirecionamentos.")


def _meta(soup: BeautifulSoup, *keys: str) -> str:
    for key in keys:
        tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if tag and tag.get("content"):
            return " ".join(str(tag["content"]).split())
    return ""


def _extract_product(url: str) -> Product:
    raw, content_type, final_url = _fetch(url, max_bytes=MAX_PAGE_BYTES)
    if "html" not in content_type.lower() and b"<html" not in raw[:1000].lower():
        raise ValueError("O link não parece apontar para uma página de produto.")
    soup = BeautifulSoup(raw, "html.parser")
    title = _meta(soup, "og:title", "twitter:title")
    if not title and soup.title and soup.title.string:
        title = " ".join(soup.title.string.split())
    description = _meta(soup, "og:description", "description", "twitter:description")
    price = _meta(soup, "product:price:amount", "og:price:amount", "twitter:data1")
    currency = _meta(soup, "product:price:currency", "og:price:currency")
    if not price:
        for selector in ("[itemprop='price']", "meta[property='product:price:amount']"):
            node = soup.select_one(selector)
            if node:
                price = str(node.get("content") or node.get_text(" ", strip=True)).strip()
                if price:
                    break
    if price and currency and currency.upper() not in price.upper():
        price = f"{price} {currency.upper()}"
    image = _meta(soup, "og:image", "twitter:image", "twitter:image:src")
    if not image:
        node = soup.find("img", src=True)
        if node:
            image = str(node["src"])
    image = urljoin(final_url, image) if image else ""
    return Product(
        title=title[:300] or urlparse(final_url).netloc,
        description=description[:600],
        price=price[:80],
        image_url=image,
        page_url=final_url,
    )


def _caption(product: Product) -> str:
    title = product.title.strip()
    lines = [f"✨ {title}"]
    if product.description:
        lines += ["", product.description]
    lines += ["", f"💰 Preço: {product.price or 'consulta o preço no link'}", f"🛍️ Ver produto: {product.page_url}", "", DEFAULT_TAGS]
    return "\n".join(lines)[:3900]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message:
        await update.message.reply_text(
            "Olá! Envia-me um link público de um produto e preparo uma publicação com os dados que a página disponibilizar.\n\n"
            "Também tento anexar a imagem principal. O link enviado será usado como link de compra; "
            "não acrescento automaticamente códigos de afiliado. Usa /help para mais informações."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message:
        await update.message.reply_text(
            "Envia um link público de produto. Vou tentar recolher título, descrição, preço e imagem a partir dos metadados da página.\n\n"
            "Os resultados dependem do site e podem precisar de correção. O bot não inicia sessão, não contorna proteções e não garante que consiga ler todas as lojas.\n"
            "O link recebido aparece na publicação como link de compra. Se precisares de um link de afiliado, envia o teu link de afiliado já preparado."
        )


async def product_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    message = update.message
    if not message or not message.text:
        return
    match = re.search(r"https?://\S+", message.text.strip())
    if not match:
        await message.reply_text("Envia um link completo começado por https:// ou http://.")
        return
    url = match.group(0).rstrip(".,!?)\]")
    await message.reply_text("A analisar a página…")
    try:
        product = await asyncio.to_thread(_extract_product, url)
    except (requests.RequestException, ValueError, UnicodeError) as exc:
        logger.info("Could not read product page: %s", type(exc).__name__)
        await message.reply_text(
            "Não consegui ler os dados desta página. Pode exigir JavaScript ou bloquear acessos automáticos. "
            "Confirma se o link está correto e, se necessário, envia o nome e o preço para eu preparar o texto manualmente."
        )
        return
    caption = _caption(product)
    if product.image_url:
        try:
            image_data, content_type, _ = await asyncio.to_thread(
                _fetch, product.image_url, max_bytes=MAX_IMAGE_BYTES
            )
            if content_type.lower().startswith("image/"):
                await message.reply_photo(photo=image_data, caption=caption)
                return
        except (requests.RequestException, ValueError, OSError) as exc:
            logger.info("Could not fetch product image: %s", type(exc).__name__)
    await message.reply_text(caption, disable_web_page_preview=False)


def main() -> None:
    if not TOKEN:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN. Copia .env.example para .env e adiciona o token do BotFather.")
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, product_link))
    logger.info("Hacoo Affiliate Bot está a iniciar.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
