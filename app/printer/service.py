"""
Serviço de impressora térmica POS58 — ESC/POS
Backend primário: win32print nativo (Windows)
Outros backends: USB direto, Rede TCP/IP, Serial/COM via escpos
"""
from __future__ import annotations
import json, logging, math, queue, threading
from datetime import datetime
from pathlib import Path

try:
    import usb.core
    import usb.util
    _USB_DISPONIVEL = True
except Exception:
    _USB_DISPONIVEL = False

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "printer_config.json"
# Raiz do projeto (três níveis acima de app/printer/service.py)
BASE_DIR = Path(__file__).parent.parent.parent

_fila: queue.Queue = queue.Queue()
_worker_iniciado   = False
_lock              = threading.Lock()

ESC = b'\x1b'
GS  = b'\x1d'

CMD_INIT         = ESC + b'@'
CMD_BOLD_ON      = ESC + b'E\x01'
CMD_BOLD_OFF     = ESC + b'E\x00'
CMD_ALIGN_LEFT   = ESC + b'a\x00'
CMD_ALIGN_CENTER = ESC + b'a\x01'
CMD_ALIGN_RIGHT  = ESC + b'a\x02'
CMD_CUT          = GS  + b'V\x41\x00'


# ═══════════════════════════════════════════════════════════════════════
# Logo em bitmap ESC/POS (GS v 0 — raster)
# ═══════════════════════════════════════════════════════════════════════

def _logo_para_bytes(logo_url: str, largura_max: int = 300) -> bytes | None:
    """
    Converte a logo do sistema em bytes ESC/POS raster (GS v 0).
    - logo_url: URL relativa como '/static/uploads/logo.png'
    - largura_max: largura máxima em pontos (300 cabe em 58mm e 80mm)
    Retorna None se Pillow não estiver disponível ou a logo não existir.
    """
    try:
        from PIL import Image
    except ImportError:
        logger.warning("Pillow não instalado — logo não será impressa.")
        return None

    if not logo_url:
        return None

    # Converte URL relativa → caminho absoluto no disco
    caminho = BASE_DIR / logo_url.lstrip("/").replace("/", str(Path.cwd().anchor)[0])
    # Forma mais simples e portável:
    partes = logo_url.lstrip("/").split("/")   # ['static', 'uploads', 'logo.png']
    caminho = BASE_DIR.joinpath(*partes)

    if not caminho.exists():
        logger.warning("Logo não encontrada em %s", caminho)
        return None

    try:
        img = Image.open(caminho).convert("L")   # grayscale

        # Redimensiona mantendo proporção
        if img.width > largura_max:
            altura = int(img.height * largura_max / img.width)
            img = img.resize((largura_max, altura), Image.LANCZOS)

        # Garante largura múltipla de 8 (exigência ESC/POS)
        largura = (img.width + 7) & ~7
        if largura != img.width:
            fundo = Image.new("L", (largura, img.height), 255)
            fundo.paste(img, ((largura - img.width) // 2, 0))
            img = fundo

        # Binariza (threshold 128 — pixels escuros = imprimir)
        img = img.point(lambda p: 0 if p < 128 else 255)

        bytes_por_linha = largura // 8
        altura          = img.height

        xL = bytes_por_linha & 0xFF
        xH = (bytes_por_linha >> 8) & 0xFF
        yL = altura & 0xFF
        yH = (altura >> 8) & 0xFF

        # GS v 0 — m=0 (densidade normal)
        buf = bytearray(b'\x1d\x76\x30\x00') + bytes([xL, xH, yL, yH])

        pixels = img.load()
        for y in range(altura):
            for bx in range(bytes_por_linha):
                byte = 0
                for bit in range(8):
                    x = bx * 8 + bit
                    if x < largura and pixels[x, y] == 0:
                        byte |= (1 << (7 - bit))
                buf.append(byte)

        return bytes(buf)

    except Exception as exc:
        logger.warning("Erro ao converter logo: %s", exc)
        return None


# ═══════════════════════════════════════════════════════════════════════
# Montar bytes ESC/POS a partir de linhas de texto
# ═══════════════════════════════════════════════════════════════════════

def _linha_para_bytes(texto: str) -> bytes:
    """
    Converte texto com marcadores inline [B]...[/B] em bytes ESC/POS.
    Suporta bold parcial dentro de uma linha.
    """
    import re
    buf = bytearray()
    partes = re.split(r'(\[B\]|\[/B\])', texto)
    negrito = False
    for parte in partes:
        if parte == '[B]':
            negrito = True
            buf += CMD_BOLD_ON
        elif parte == '[/B]':
            negrito = False
            buf += CMD_BOLD_OFF
        elif parte:
            buf += parte.encode("cp850", errors="replace")
    if negrito:
        buf += CMD_BOLD_OFF
    return bytes(buf)


def _montar_bytes(linhas: list[str], cortar: bool,
                  logo_bytes: bytes | None = None) -> bytes:
    """
    Converte lista de linhas com marcadores em bytes ESC/POS.

    Marcadores suportados:
      [C]        → alinha ao centro
      [R]        → alinha à direita
      [B]        → bold na linha inteira (quando é prefixo)
      [B]...[/B] → bold inline parcial
      [CUT]      → guilhotina
    """
    buf = bytearray(CMD_INIT)

    # Logo centralizada no topo
    if logo_bytes:
        buf += CMD_ALIGN_CENTER
        buf += logo_bytes
        buf += b'\n'

    for linha in linhas:
        if linha == "[CUT]":
            buf += CMD_CUT
            continue

        # Alinhamento
        if linha.startswith("[C]"):
            buf += CMD_ALIGN_CENTER
            texto = linha[3:]
        elif linha.startswith("[R]"):
            buf += CMD_ALIGN_RIGHT
            texto = linha[3:]
        else:
            buf += CMD_ALIGN_LEFT
            texto = linha

        # Bold de linha inteira (prefixo [B] sem [/B] no meio)
        tem_inline_bold = "[/B]" in texto or (
            "[B]" in texto and not texto.startswith("[B]")
        )

        if texto.startswith("[B]") and not tem_inline_bold:
            buf += CMD_BOLD_ON
            buf += texto[3:].encode("cp850", errors="replace") + b'\n'
            buf += CMD_BOLD_OFF
        elif tem_inline_bold or "[B]" in texto:
            # Bold inline parcial
            buf += CMD_BOLD_OFF
            buf += _linha_para_bytes(texto) + b'\n'
        else:
            buf += CMD_BOLD_OFF
            buf += texto.encode("cp850", errors="replace") + b'\n'

    buf += CMD_BOLD_OFF + CMD_ALIGN_LEFT
    if cortar:
        buf += CMD_CUT

    return bytes(buf)


# ═══════════════════════════════════════════════════════════════════════
# Buscar configurações da loja
# ═══════════════════════════════════════════════════════════════════════

def _config_loja() -> dict:
    """Retorna nome_lanchonete e logo_url do banco. Nunca lança exceção."""
    try:
        from app.repositories.config_repository import buscar_configuracoes
        cfg = buscar_configuracoes()
        return {
            "nome": cfg.get("nome_lanchonete") or "Lanchonete",
            "logo_url": cfg.get("logo_url") or "",
        }
    except Exception as exc:
        logger.warning("Erro ao buscar config da loja: %s", exc)
        return {"nome": "Lanchonete", "logo_url": ""}


# ═══════════════════════════════════════════════════════════════════════
# Formatação do cupom de pedido
# ═══════════════════════════════════════════════════════════════════════

def _fmt_brl(valor: float) -> str:
    """Formata valor monetário no padrão brasileiro: R$ X.XXX,XX"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _col_lr(esquerda: str, direita: str, largura: int = 32) -> str:
    """Alinha texto à esquerda e valor à direita na mesma linha."""
    espacos = largura - len(esquerda) - len(direita)
    return f"{esquerda}{' ' * max(espacos, 1)}{direita}"


def formatar_cupom_pedido(pedido: dict) -> list[str]:
    """
    Gera as linhas do cupom para impressão térmica POS58 (32 colunas).
    Layout:
      ★ NOME DA LOJA ★   (centralizado, negrito)
      DD/MM/AAAA HH:MM   (centralizado)
      --------------------------------
      PEDIDO #N  ENTREGA  (centralizado, negrito)
      --------------------------------
      Cliente
      Nome do cliente     (negrito)
      Telefone
      Bairro – Endereço
      --------------------------------
      ITENS
      Nx Produto
        + Complemento
                   R$ X,XX
      --------------------------------
      Taxa de entrega     R$ X,XX
      TOTAL               R$ X,XX  (negrito)
      --------------------------------
      Pagamento [B]Metodo[/B]
      Valor pago          R$ X,XX
      Troco               R$ X,XX  (negrito)
      --------------------------------
      Obrigado pela preferencia!  (centralizado)
    """
    loja = _config_loja()
    nome_loja = loja["nome"].upper()

    SEP  = "--------------------------------"
    COLS = 32

    pid        = pedido.get("id", "")
    cliente    = pedido.get("cliente_nome") or pedido.get("nome", "Cliente")
    telefone   = pedido.get("cliente_telefone") or pedido.get("telefone", "")
    endereco   = (pedido.get("endereco") or "").strip()
    bairro     = (pedido.get("bairro") or "").strip()
    metodo_raw = (pedido.get("metodo_pagamento") or pedido.get("metodo") or "Dinheiro")
    metodo     = metodo_raw.capitalize()
    total      = float(pedido.get("total_geral") or pedido.get("total") or 0)
    taxa       = float(pedido.get("taxa_entrega") or pedido.get("taxa") or 0)
    valor_pago = pedido.get("valor_pago")

    # Data/hora
    data_hora = pedido.get("data_hora") or pedido.get("data", "")
    try:
        dt = datetime.fromisoformat(str(data_hora)) if data_hora else datetime.now()
        data_fmt = dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        data_fmt = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Tipo de entrega
    eh_entrega = bool(
        bairro or (endereco and endereco.lower() not in ("retirada", "retirada no local", ""))
    )
    tipo_entrega = "ENTREGA" if eh_entrega else "RETIRADA"

    # ── Cabeçalho ──────────────────────────────────────────────────────
    linhas: list[str] = [
        f"[C][B]* {nome_loja} *",
        f"[C]{data_fmt}",
        SEP,
        f"[C][B]PEDIDO #{pid}   {tipo_entrega}",
        SEP,
    ]

    # ── Cliente ────────────────────────────────────────────────────────
    linhas.append("Cliente")
    linhas.append(f"[B]{cliente}")
    if telefone:
        linhas.append(telefone)

    if eh_entrega:
        partes_end = []
        if bairro:
            partes_end.append(bairro)
        if endereco:
            partes_end.append(endereco)
        if partes_end:
            linhas.append(" - ".join(partes_end))
    else:
        linhas.append("Retirada no balcao")

    # ── Itens ──────────────────────────────────────────────────────────
    linhas.append(SEP)
    linhas.append("[B]ITENS")

    for item in pedido.get("itens", []):
        nome        = item.get("produto_nome") or item.get("nome", "Item")
        qtd         = int(item.get("quantidade", 1))
        preco       = float(item.get("preco_unitario") or item.get("preco") or 0)
        subtot_item = qtd * preco

        linhas.append(f"{qtd}x {nome}")

        for comp in item.get("complementos", []):
            nome_c = comp.get("nome") or comp.get("produto_nome", "")
            qtd_c  = int(comp.get("quantidade", 1))
            if nome_c:
                prefixo = f"  + {qtd_c}x " if qtd_c > 1 else "  + "
                linhas.append(f"{prefixo}{nome_c}")

        # Preço do item alinhado à direita
        linhas.append(_fmt_brl(subtot_item).rjust(COLS))
        linhas.append(SEP)

    # ── Totais ─────────────────────────────────────────────────────────
    if taxa > 0:
        linhas.append(_col_lr("Taxa de entrega", _fmt_brl(taxa), COLS))

    linhas.append(f"[B]{_col_lr('TOTAL', _fmt_brl(total), COLS)}")
    linhas.append(SEP)

    # ── Pagamento ──────────────────────────────────────────────────────
    linhas.append(f"Pagamento [B]{metodo}[/B]")

    if valor_pago is not None:
        vp    = float(valor_pago)
        troco = vp - total
        linhas.append(_col_lr("Valor pago", _fmt_brl(vp), COLS))
        if troco >= 0:
            linhas.append(f"[B]{_col_lr('Troco', _fmt_brl(troco), COLS)}")

    linhas += [
        SEP,
        "[C]Obrigado pela preferencia!",
        "[CUT]",
    ]

    return linhas


# ═══════════════════════════════════════════════════════════════════════
# Configuração da impressora
# ═══════════════════════════════════════════════════════════════════════

def carregar_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "tipo": "windows", "modo": "automatico", "nome_windows": None,
        "vendor_id": "", "product_id": "", "ip": "", "porta": 9100,
        "com": "", "baudrate": 9600, "cortar_papel": True,
    }


def salvar_config(dados: dict) -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config = carregar_config()
    config.update(dados)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    return config


def listar_impressoras_windows() -> list[str]:
    try:
        import win32print
        printers = win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        )
        return [p[2] for p in printers]
    except ImportError:
        import subprocess
        try:
            r = subprocess.run(["wmic", "printer", "get", "name"],
                               capture_output=True, text=True, timeout=5)
            return [l.strip() for l in r.stdout.splitlines()
                    if l.strip() and l.strip() != "Name"]
        except Exception:
            return []
    except Exception:
        return []


def _detectar_usb() -> list[dict]:
    if not _USB_DISPONIVEL:
        return []
    try:
        resultado = []
        for dev in usb.core.find(find_all=True):
            try:
                resultado.append({
                    "vendor_id":  f"0x{dev.idVendor:04x}",
                    "product_id": f"0x{dev.idProduct:04x}",
                    "fabricante": usb.util.get_string(dev, dev.iManufacturer) if dev.iManufacturer else "",
                    "produto":    usb.util.get_string(dev, dev.iProduct) if dev.iProduct else "",
                })
            except Exception:
                pass
        return resultado
    except Exception as exc:
        logger.warning("Erro ao detectar USB: %s", exc)
        return []


def listar_impressoras() -> list[dict]:
    resultado = [{"tipo": "windows", "nome": n} for n in listar_impressoras_windows()]
    resultado.extend({**dev, "tipo": "usb"} for dev in _detectar_usb())
    return resultado


# ═══════════════════════════════════════════════════════════════════════
# Impressão
# ═══════════════════════════════════════════════════════════════════════

def _imprimir_windows(nome: str, dados: bytes) -> None:
    import win32print
    hPrinter = win32print.OpenPrinter(nome)
    try:
        hJob = win32print.StartDocPrinter(hPrinter, 1, ("Cupom", None, "RAW"))
        try:
            win32print.StartPagePrinter(hPrinter)
            win32print.WritePrinter(hPrinter, dados)
            win32print.EndPagePrinter(hPrinter)
        finally:
            win32print.EndDocPrinter(hPrinter)
    finally:
        win32print.ClosePrinter(hPrinter)


def _imprimir_escpos_outros(config: dict, dados: bytes) -> None:
    from escpos import printer as ep
    tipo = config.get("tipo", "windows").lower()
    if tipo == "usb":
        p = ep.Usb(int(config.get("vendor_id") or "0x0416", 16),
                   int(config.get("product_id") or "0x5011", 16))
    elif tipo == "rede":
        host = config.get("ip") or ""
        if not host:
            raise ValueError("IP da impressora não configurado.")
        p = ep.Network(host, int(config.get("porta") or 9100))
    elif tipo == "serial":
        com = config.get("com") or ""
        if not com:
            raise ValueError("Porta COM não configurada.")
        p = ep.Serial(com, baudrate=int(config.get("baudrate") or 9600))
    else:
        raise ValueError(f"Tipo desconhecido: {tipo!r}")
    p._raw(dados)
    p.close()


def _imprimir(config: dict, linhas: list[str],
              com_logo: bool = True) -> dict:
    """
    Monta os bytes e envia para a impressora.
    com_logo=True tenta carregar e imprimir a logo do sistema acima do texto.
    """
    tipo   = (config.get("tipo") or "windows").lower()
    cortar = config.get("cortar_papel", True)

    logo_bytes = None
    if com_logo:
        loja = _config_loja()
        logo_bytes = _logo_para_bytes(loja["logo_url"])

    dados = _montar_bytes(linhas, cortar, logo_bytes=logo_bytes)

    try:
        if tipo == "windows":
            nome = config.get("nome_windows") or ""
            if not nome:
                raise ValueError("Nenhuma impressora Windows selecionada.")
            _imprimir_windows(nome, dados)
        else:
            _imprimir_escpos_outros(config, dados)
        return {"ok": True}
    except Exception as e:
        logger.exception("Erro na impressão:")
        return {"ok": False, "mensagem": str(e)}


def testar_impressora() -> dict:
    loja   = _config_loja()
    config = carregar_config()
    conteudo = [
        "================================",
        f"[C][B]{loja['nome'].upper()}",
        "[C]** TESTE DE IMPRESSAO **",
        "================================",
        "[C]Sistema OK",
        "[CUT]",
    ]
    resultado = _imprimir(config, conteudo, com_logo=True)
    if resultado["ok"]:
        resultado["mensagem"] = "Página de teste enviada com sucesso."
    return resultado


def imprimir_cupom(job: list[str] | str | dict) -> dict:
    """Imprime imediatamente. Aceita dict de pedido, list[str] ou str."""
    config = carregar_config()
    if isinstance(job, dict):
        linhas = formatar_cupom_pedido(job)
    elif isinstance(job, str):
        linhas = job.splitlines()
    else:
        linhas = job
    return _imprimir(config, linhas, com_logo=True)


def enfileirar_impressao(job: list[str] | str | dict) -> None:
    """Enfileira para impressão assíncrona."""
    _fila.put(job)


def _loop_worker() -> None:
    logger.info("Worker POS58 iniciado.")
    while True:
        try:
            job = _fila.get(timeout=2)
        except queue.Empty:
            continue
        try:
            r = imprimir_cupom(job)
            if not r["ok"]:
                logger.error("Falha na impressão: %s", r.get("mensagem"))
        except Exception:
            logger.exception("Erro no worker de impressão.")
        finally:
            _fila.task_done()


def iniciar_worker() -> None:
    global _worker_iniciado
    with _lock:
        if _worker_iniciado:
            return
        t = threading.Thread(target=_loop_worker, name="pos58-worker", daemon=True)
        t.start()
        _worker_iniciado = True
        logger.info("Thread pos58-worker iniciada.")
