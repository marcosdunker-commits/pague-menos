import streamlit as st
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
from bs4 import BeautifulSoup
import re
import json

st.set_page_config(page_title="Pague Menos - Editor", page_icon="🛍️", layout="centered")

LOGO_PATH = "logo.jpg"
SEAL_PATH = "selo.png"


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


def get_image_url(url):
    r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
    r.raise_for_status()
    html = r.text

    # 1. og:image via regex (suporta qualquer ordem de atributos)
    og_match = re.search(r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
    if not og_match:
        og_match = re.search(r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']', html)
    if og_match:
        val = og_match.group(1)
        if not val.startswith("data:"):
            return val

    # 2. Imagens mlstatic de alta qualidade (-O. ou -OO.)
    imgs = re.findall(r'https://http2\.mlstatic\.com/\S+?(?:-O\.webp|-OO\.webp|-O\.jpg|-O\.jpeg)', html)
    if imgs:
        return imgs[0]

    # 3. Qualquer imagem mlstatic
    imgs = re.findall(r'https://http2\.mlstatic\.com/\S+?\.(?:webp|jpg|jpeg)', html)
    if imgs:
        return imgs[0]

    # 4. Amazon
    imgs = re.findall(r'https://m\.media-amazon\.com/images/I/[A-Za-z0-9%+_.-]+\.(?:jpg|jpeg|png|webp)', html)
    if imgs:
        for img in imgs:
            if not re.search(r'_AC_|_SX|_SY|_CR|_UL|_SS|_SR', img):
                return img
        return imgs[0]

    imgs = re.findall(r'https://images-na\.ssl-images-amazon\.com/images/I/[A-Za-z0-9%+_.-]+\.(?:jpg|jpeg|png)', html)
    if imgs:
        return imgs[0]

    # 5. Shopee
    imgs = re.findall(r'https://cf\.shopee\.com\.br/file/[A-Za-z0-9_-]+', html)
    if imgs:
        return imgs[0]

    # 6. Magalu / Magazine Luiza
    imgs = re.findall(r'https://a-static\.mlcdn\.com\.br/[^\s"\']+\.(?:jpg|jpeg|png|webp)', html)
    if imgs:
        return imgs[0]

    # 7. Americanas / Submarino / Shoptime
    imgs = re.findall(r'https://[^\s"\']*\.americanas\.com\.br/[^\s"\']+\.(?:jpg|jpeg|png)', html)
    if not imgs:
        imgs = re.findall(r'https://[^\s"\']*images[^\s"\']+\.(?:jpg|jpeg|png)', html)
    if imgs:
        return imgs[0]

    # 8. AliExpress
    imgs = re.findall(r'https://ae\d+\.alicdn\.com/kf/[^\s"\']+\.(?:jpg|jpeg|png|webp)', html)
    if imgs:
        return imgs[0]

    return None


def download_image(url):
    r = requests.get(url, headers=HEADERS, timeout=15)
    return Image.open(BytesIO(r.content)).convert("RGB")


def draw_stars(draw, x, y, rating, size=50, color=(255, 200, 0)):
    import math
    for i in range(5):
        filled = i < round(rating)
        cx = x + i * (size + 10) + size // 2
        cy = y + size // 2
        pts = []
        for j in range(10):
            angle = math.pi / 2 + j * 2 * math.pi / 10
            r = size // 2 if j % 2 == 0 else size // 4
            pts.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
        if filled:
            draw.polygon(pts, fill=color)
        else:
            draw.polygon(pts, outline=color, width=2)


def get_font(size, bold=False):
    if bold:
        candidates = [
            "arialbd.ttf",
            "arial.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    else:
        candidates = [
            "arial.ttf",
            "arialbd.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def get_font_italic(size):
    candidates = [
        "ariali.ttf",
        "Arial Italic.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "arial.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def remove_white_bg(img, threshold=240):
    img = img.convert("RGBA")
    data = img.getdata()
    new_data = []
    for r, g, b, a in data:
        if r >= threshold and g >= threshold and b >= threshold:
            new_data.append((r, g, b, 0))
        else:
            new_data.append((r, g, b, a))
    img.putdata(new_data)
    return img


def remove_black_bg(img, threshold=40):
    img = img.convert("RGBA")
    data = img.getdata()
    new_data = []
    for r, g, b, a in data:
        if r < threshold and g < threshold and b < threshold:
            new_data.append((r, g, b, 0))
        else:
            new_data.append((r, g, b, a))
    img.putdata(new_data)
    return img


def get_impact(size):
    for name in ["impact.ttf", "Impact.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return get_font(size, bold=True)


def draw_outlined_text(draw, pos, text, font, fill, outline, thickness=3):
    x, y = pos
    for dx in range(-thickness, thickness + 1):
        for dy in range(-thickness, thickness + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=outline)
    draw.text((x, y), text, font=font, fill=fill)


def draw_neon_text(canvas, pos, text, font, color=(255, 230, 0)):
    x, y = pos
    # Camadas de brilho neon (múltiplos blurs)
    for radius, alpha in [(18, 60), (10, 100), (5, 160)]:
        glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).text((x, y), text, font=font, fill=(*color, alpha))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=radius))
        canvas.paste(Image.alpha_composite(canvas.convert("RGBA"), glow).convert("RGB"))
    # Texto nítido por cima
    ImageDraw.Draw(canvas).text((x, y), text, font=font, fill=color)
    # Reflexo branco no topo (brilho)
    highlight = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(highlight).text((x, y - 1), text, font=font, fill=(255, 255, 255, 90))
    canvas.paste(Image.alpha_composite(canvas.convert("RGBA"), highlight).convert("RGB"))


def create_product_image(product_img, rating, review_count):
    W = 1080
    product_h = 810
    banner_area_h = 310
    footer_h = 150
    H = product_h + banner_area_h + footer_h
    bm = 22

    # Fundo branco até quase o meio do banner, azul abaixo
    by1 = product_h + 18
    by2 = product_h + banner_area_h - 18
    blue_start = by1 + (by2 - by1) // 4  # 1/4 do banner
    canvas = Image.new("RGB", (W, H), "white")
    bg_draw = ImageDraw.Draw(canvas)
    lower_h = H - blue_start
    for y in range(lower_h):
        t = y / lower_h
        # Azul bem claro no topo → azul bem escuro embaixo
        r = int(150 + (4  - 150) * t)
        g = int(200 + (10 - 200) * t)
        b = int(255 + (40 - 255) * t)
        bg_draw.line([(0, blue_start + y), (W, blue_start + y)], fill=(r, g, b))

    # Produto centralizado em fundo branco
    product_bg = Image.new("RGB", (W, product_h), "white")
    img = product_img.copy()
    ratio = min((W - 60) / img.width, (product_h - 60) / img.height)
    new_w = int(img.width * ratio)
    new_h = int(img.height * ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    product_bg.paste(img, ((W - new_w) // 2, (product_h - new_h) // 2))
    canvas.paste(product_bg, (0, 0))

    draw = ImageDraw.Draw(canvas)

    # Banner arredondado com degradê próprio (como antes)
    by1 = product_h + 18
    by2 = product_h + banner_area_h - 18
    bw = W - 2 * bm
    bh = by2 - by1
    banner_img = Image.new("RGB", (bw, bh))
    bn_draw = ImageDraw.Draw(banner_img)
    for y in range(bh):
        t = y / bh
        r = int(20 + (80 - 20) * t)
        g = int(80 + (10 - 80) * t)
        b = int(220 + (90 - 220) * t)
        bn_draw.line([(0, y), (bw, y)], fill=(r, g, b))
    mask = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (bw - 1, bh - 1)], radius=28, fill=255)
    canvas.paste(banner_img, (bm, by1), mask)

    draw = ImageDraw.Draw(canvas)
    pad = 40
    mid_y = (by1 + by2) // 2

    if rating > 0:
        f_num = get_font(95, bold=True)
        rating_str = f"{rating:.1f}"
        num_w = int(draw.textlength(rating_str, font=f_num))
        draw.text((bm + pad, mid_y - 55), rating_str, fill=(255, 200, 0), font=f_num)
        draw_stars(draw, bm + pad + num_w + 25, mid_y - 38, rating, size=55)

        if review_count >= 1000:
            rv_str = f"{review_count / 1000:.1f}mil".replace(".0mil", "mil")
        else:
            rv_str = str(review_count) if review_count else ""
        if rv_str:
            f_rv = get_font(52, bold=True)
            f_av = get_font(28)
            rv_w = int(draw.textlength(rv_str, font=f_rv))
            av_w = int(draw.textlength("AVALIAÇÕES", font=f_av))
            draw.text((W - bm - pad - rv_w, mid_y - 45), rv_str, fill="white", font=f_rv)
            draw.text((W - bm - pad - av_w, mid_y + 18), "AVALIAÇÕES", fill="white", font=f_av)
    else:
        f_sl = get_font(38, bold=True)
        sl_w = int(draw.textlength("CUPONS QUE FAZEM A DIFERENÇA!", font=f_sl))
        draw.text(((W - sl_w) // 2, mid_y - 22), "CUPONS QUE FAZEM A DIFERENÇA!", fill=(255, 200, 0), font=f_sl)

    # Rodapé — sem cor separada, usa o fundo unificado
    fy = product_h + banner_area_h

    # Logo à direita
    try:
        logo = remove_black_bg(Image.open(LOGO_PATH))
        logo.thumbnail((180, footer_h - 8), Image.LANCZOS)
        logo_x = W - logo.width - 15
        canvas.paste(logo, (logo_x, fy + (footer_h - logo.height) // 2), logo)
    except Exception:
        logo_x = W - 15

    logo_zone_start = W - 200

    # Selo no centro
    seal_size = footer_h - 10
    seal_zone_start = logo_zone_start
    try:
        seal = remove_white_bg(Image.open(SEAL_PATH))
        seal.thumbnail((seal_size, seal_size), Image.LANCZOS)
        seal_zone_start = logo_zone_start - seal.width - 20
        seal_x = seal_zone_start + 10
        seal_y = fy + (footer_h - seal.height) // 2
        canvas.paste(seal, (seal_x, seal_y), seal)
    except Exception:
        pass

    # Frase à esquerda
    linha = "PAGUE MENOS CUPOM DE VERDADE"
    area_start = 15
    area_w = seal_zone_start - area_start - 10
    font_size = int(footer_h * 0.21)
    while font_size > 8:
        f2 = get_font_italic(font_size)
        if int(draw.textlength(linha, font=f2)) <= area_w:
            break
        font_size -= 1
    txt_w = int(draw.textlength(linha, font=f2))
    txt_x = area_start + (area_w - txt_w) // 2
    txt_y = fy + (footer_h - font_size) // 2
    draw.text((txt_x, txt_y), linha, font=f2, fill=(255, 255, 255), stroke_width=0)

    return canvas


# --- Interface ---
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image("logo_transparent.png", width=90)
with col_title:
    st.title("Pague Menos - Editor de Fotos")
    st.caption("Cole o link do Mercado Livre e baixe a foto pronta com sua marca.")

url = st.text_input("🔗 Link do produto:", placeholder="Mercado Livre, Amazon, Shopee, Magalu, Americanas, AliExpress...")

col1, col2 = st.columns(2)
with col1:
    rating = st.number_input("⭐ Avaliação (0 = não mostrar)", min_value=0.0, max_value=5.0, value=0.0, step=0.1)
with col2:
    review_count = st.number_input("💬 Nº de avaliações", min_value=0, value=0, step=1)

st.divider()
st.subheader("📝 Texto para o WhatsApp")

titulo = st.text_input("🔥 Título chamativo:", placeholder="Ex: 50 UNIDADES PRA ORGANIZAR DE VEZ")
produto = st.text_input("✅ Nome do produto:", placeholder="Ex: Kit 50 Cabides Veludo")

col3, col4 = st.columns(2)
with col3:
    preco_de = st.text_input("Preço DE:", placeholder="Ex: 109,90")
with col4:
    preco_por = st.text_input("Preço POR:", placeholder="Ex: 56,84")

if url and st.button("🖼️ Gerar foto e texto"):
    with st.spinner("Buscando produto..."):
        try:
            img_url = get_image_url(url)

            if not img_url:
                st.error("Não encontrei imagem nesse link. Tente outro link do produto.")
            else:
                product_img = download_image(img_url)
                result = create_product_image(product_img, rating, review_count)

                st.image(result, use_container_width=True)

                buf = BytesIO()
                result.save(buf, format="JPEG", quality=95)
                buf.seek(0)

                st.success("Foto pronta!")
                st.download_button(
                    "⬇️ Baixar foto",
                    buf,
                    file_name="paguemenos_produto.jpg",
                    mime="image/jpeg",
                )

                # Texto para WhatsApp
                partes = []
                if titulo:
                    partes.append(f"🔥 *{titulo.upper()}*")
                if produto:
                    partes.append(f"✅ {produto}")
                if preco_de and preco_por:
                    partes.append(f"💰 DE R$ ~{preco_de}~ | *POR R$ {preco_por}*")
                elif preco_por:
                    partes.append(f"💰 *POR R$ {preco_por}*")
                partes.append(f"🔗 {url}")

                texto = "\n\n".join(partes)

                st.divider()
                st.subheader("📋 Copie o texto abaixo:")
                st.code(texto, language=None)

        except Exception as e:
            st.error(f"Erro: {e}")

st.divider()
st.caption("Desenvolvido por Marcos Dunker")
