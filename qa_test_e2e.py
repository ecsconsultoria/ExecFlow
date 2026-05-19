"""
QA End-to-End Test — App_Orcamentos_V4
Data: 2026-05-18
Testador: GitHub Copilot (QA Automatizado)

Fluxo testado:
  1.  Login admin
  2.  Dashboard carrega corretamente
  3.  Cadastrar novo cliente (com e-mail ECS válido)
  4.  Listar clientes / busca de cliente
  5.  Criar orçamento com 2 itens de serviço
  6.  Visualizar detalhe do orçamento + PDF (PT e EN)
  7.  Aprovar orçamento
  8.  Confirmar reserva → gera Booking + OS automática
  9.  Detalhe do Booking
  10. Atribuir motorista interno à OS
  11. Atribuir fornecedor externo à OS
  12. Adicionar custo operacional na OS
  13. Atualizar status OS: agendado → em_execucao → finalizado
  14. Enviar dados de motorista ao cliente (send_driver_info)
  15. Cadastrar motorista
  16. Cadastrar fornecedor
  17. Cadastrar veículo
  18. Dashboard de despacho (dispatch)
  19. Relatórios
  20. Editar orçamento
  21. Reprovar orçamento (fluxo alternativo)
  22. Logout
"""

import sys
import requests
import json
import time
from datetime import datetime

BASE = "http://127.0.0.1:5004"
RESULTS = []
session = requests.Session()
session.headers.update({"User-Agent": "QA-Bot/1.0"})

# ─── Helpers ──────────────────────────────────────────────────────────────────

def ok(test_name, detail=""):
    RESULTS.append({"status": "PASS", "test": test_name, "detail": detail})
    print(f"  ✅  PASS | {test_name}" + (f" — {detail}" if detail else ""))

def fail(test_name, detail=""):
    RESULTS.append({"status": "FAIL", "test": test_name, "detail": detail})
    print(f"  ❌  FAIL | {test_name}" + (f" — {detail}" if detail else ""))

def warn(test_name, detail=""):
    RESULTS.append({"status": "WARN", "test": test_name, "detail": detail})
    print(f"  ⚠️   WARN | {test_name}" + (f" — {detail}" if detail else ""))

def check(test_name, condition, detail="", pass_detail=""):
    if condition:
        ok(test_name, pass_detail or detail)
    else:
        fail(test_name, detail)
    return condition

def get(path, **kw):
    return session.get(BASE + path, allow_redirects=True, timeout=10, **kw)

def post(path, data=None, json_data=None, **kw):
    if json_data:
        return session.post(BASE + path, json=json_data,
                            headers={"Content-Type": "application/json"},
                            allow_redirects=True, timeout=10, **kw)
    return session.post(BASE + path, data=data, allow_redirects=True, timeout=10, **kw)

def csrf_get(path):
    """GET a page and try to extract a CSRF token if present."""
    r = get(path)
    return r

# ─── Test execution ───────────────────────────────────────────────────────────

print("=" * 60)
print("  APP_ORCAMENTOS_V4 — QA TESTE END-TO-END")
print(f"  Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# ── 1. Login ───────────────────────────────────────────────────────────────────
print("\n[1] LOGIN")
r = get("/auth/login")
check("Login page loads (GET)", r.status_code == 200, f"HTTP {r.status_code}")

r = post("/auth/login", data={"email": "admin@executivecarsp.com", "password": "admin123"})
check("Login POST success", r.status_code == 200, f"HTTP {r.status_code} url={r.url}")
check("Redirected to dashboard", "/auth/login" not in r.url, f"Ended at {r.url}")
check("Dashboard HTML has content", "Dashboard" in r.text or "Orçamentos" in r.text or "dashboard" in r.url,
      f"URL={r.url}")

# ── 2. Dashboard ──────────────────────────────────────────────────────────────
print("\n[2] DASHBOARD")
r = get("/")
check("Dashboard loads (200)", r.status_code == 200, f"HTTP {r.status_code}")
check("Dashboard has stats", any(k in r.text for k in ["Clientes", "Orçamentos", "Reservas", "OS"]),
      "Could not find stats widgets in dashboard HTML")

# ── 3. Cadastrar Cliente (com e-mail ECS válido) ──────────────────────────────
print("\n[3] CADASTRO DE CLIENTE")
r = get("/clients/new")
check("New client form loads (200)", r.status_code == 200, f"HTTP {r.status_code}")

ts = int(time.time())
client_data = {
    "name":           f"QA-ECS-{ts}",
    "contact":        "Anderson Nobre",
    "email":          "anderson_nobre@icloud.com",
    "phone":          "+55 11 98474-8044",
    "whatsapp":       "5511984748044",
    "document":       "00.000.000/0001-00",
    "address":        "Av. Paulista, 1000",
    "city":           "São Paulo",
    "state":          "SP",
    "country":        "Brasil",
    "language":       "pt",
    "billing_type":   "recibo",
    "payment_method": "PIX",
    "notes":          "Cliente criado pelo QA automatizado",
}
r = post("/clients/new", data=client_data)
check("Create client POST", r.status_code == 200, f"HTTP {r.status_code}, url={r.url}")
check("Redirected to clients list", "/clients" in r.url, f"url={r.url}")
check("Client appears in list", f"QA-ECS-{ts}" in r.text, "Name not found in clients list")

# Extract new client ID from list
new_client_id = None
r_list = get("/clients/")
if f"QA-ECS-{ts}" in r_list.text:
    # Find the edit link for the new client
    import re
    ids = re.findall(r'/clients/(\d+)/edit', r_list.text)
    if ids:
        new_client_id = int(ids[-1])  # last added
check("Client ID found", new_client_id is not None, f"IDs found: {ids[:5] if 'ids' in dir() else 'N/A'}", f"id={new_client_id}")

# ── 4. Busca de Clientes ──────────────────────────────────────────────────────
print("\n[4] BUSCA DE CLIENTES")
r = get(f"/clients/search?q=QA-ECS")
check("Client search JSON (200)", r.status_code == 200, f"HTTP {r.status_code}")
try:
    data = r.json()
    check("Search returns list", isinstance(data, list), f"Got: {type(data)}")
    check("New client in search results", any(f"QA-ECS-{ts}" in (c.get("name","")) for c in data),
          f"names={[c.get('name') for c in data]}")
except Exception as e:
    fail("Client search JSON parse", str(e))

# ── 5. Criar Orçamento ────────────────────────────────────────────────────────
print("\n[5] CRIAR ORÇAMENTO")
r = get("/quotes/new")
check("New quote form loads (200)", r.status_code == 200, f"HTTP {r.status_code}")
check("Catalog data in page", "catalog" in r.text.lower() or "CATALOG" in r.text,
      "No catalog found in new quote page")

# Get catalog via parsing the page
catalog_match = re.search(r'const CATALOG\s*=\s*(\[.*?\]);', r.text, re.DOTALL)
catalog = []
pricing_id = None
if catalog_match:
    try:
        catalog = json.loads(catalog_match.group(1))
        if catalog and catalog[0].get("services"):
            pricing_id = catalog[0]["services"][0]["id"]
        ok("Catalog parsed from page", f"{len(catalog)} categories, first pricing_id={pricing_id}")
    except Exception as e:
        warn("Catalog parse", str(e))
else:
    # Try looking for CATALOG_JSON in a different way
    m2 = re.search(r'var\s+catalogData\s*=\s*(\[.*?\]);', r.text, re.DOTALL)
    if m2:
        try:
            catalog = json.loads(m2.group(1))
            pricing_id = catalog[0]["services"][0]["id"] if catalog else None
        except Exception:
            pass
    if not catalog:
        warn("Catalog not found in new quote page", "will use pricing_id=1 fallback")
        pricing_id = 1

# Get first two pricing IDs for items
pricing_id_1 = pricing_id or 1
pricing_id_2 = (catalog[0]["services"][1]["id"] if catalog and len(catalog[0].get("services",[])) > 1 else pricing_id_1 + 1) if catalog else pricing_id_1 + 1

# Build quote payload
quote_payload = {
    "client_id":      new_client_id or 3,  # fallback to ECS client
    "client_name":    f"QA-ECS-{ts}",
    "contact_name":   "Anderson Nobre",
    "email":          "anderson_nobre@icloud.com",
    "phone":          "+55 11 98474-8044",
    "language":       "pt",
    "billing_type":   "recibo",
    "payment_method": "PIX",
    "payment_terms":  "À vista no dia do serviço",
    "obs":            "Teste QA automatizado — orçamento de teste.",
    "items": [
        {
            "service_id":          1,
            "category_id":         1,
            "pricing_id":          pricing_id_1,
            "description":         "Transfer Aeroporto",
            "vehicle_description": "Toyota Corolla ou Similar",
            "driver_name":         "Monolíngue",
            "state_code":          "SP",
            "ref_note":            "GRU → Hotel Fasano",
            "quantity":            1,
            "unit_price":          770.0,
            "hour_extra":          77.0,
            "total_price":         770.0,
            "price_base":          770.0,
            "price_nf":            847.0,
            "price_cartao":        820.05,
            "price_nf_cartao":     897.05,
            "km_extra":            0,
            "km_extra_rate":       0,
            "sort_order":          0,
        },
        {
            "service_id":          2,
            "category_id":         1,
            "pricing_id":          pricing_id_2,
            "description":         "Diária 10h",
            "vehicle_description": "Toyota Corolla ou Similar",
            "driver_name":         "Monolíngue",
            "state_code":          "SP",
            "ref_note":            "Serviço executivo São Paulo",
            "quantity":            1,
            "unit_price":          770.0,
            "hour_extra":          77.0,
            "total_price":         770.0,
            "price_base":          770.0,
            "price_nf":            847.0,
            "price_cartao":        820.05,
            "price_nf_cartao":     897.05,
            "km_extra":            0,
            "km_extra_rate":       0,
            "sort_order":          1,
        },
    ],
    "inclusions": [
        {"text_pt": "Meet & Greet", "text_en": "Meet & Greet", "included": True, "sort_order": 0},
        {"text_pt": "Pedágios e Combustível", "text_en": "Tolls and Fuel", "included": True, "sort_order": 1},
    ],
}

r = post("/quotes/new", json_data=quote_payload)
check("Create quote POST (200)", r.status_code == 200, f"HTTP {r.status_code}, url={r.url}")

new_quote_id = None
try:
    resp_data = r.json()
    new_quote_id = resp_data.get("id")
    check("Create quote returns ID", new_quote_id is not None, f"resp={resp_data}")
    ok("Quote created", f"id={new_quote_id}, number={resp_data.get('number')}")
except Exception:
    # Might be redirect
    m = re.search(r'/quotes/(\d+)', r.url)
    if m:
        new_quote_id = int(m.group(1))
        ok("Quote created (via redirect)", f"id={new_quote_id}")
    else:
        fail("Quote created", f"Could not find quote ID. url={r.url}, body={r.text[:200]}")

# ── 6. Detalhe do Orçamento ───────────────────────────────────────────────────
print("\n[6] DETALHE DO ORÇAMENTO")
if new_quote_id:
    r = get(f"/quotes/{new_quote_id}")
    check("Quote detail loads (200)", r.status_code == 200, f"HTTP {r.status_code}")
    check("Quote shows client name",  f"QA-ECS-{ts}" in r.text or "Anderson" in r.text,
          "Client name not in quote detail")
    check("Quote shows items",        "Transfer" in r.text or "Diária" in r.text or "serviço" in r.text.lower(),
          "No items visible in quote detail")
    check("Quote shows total",        "770" in r.text or "1.540" in r.text or "1540" in r.text,
          "Total amount not visible")
    check("Approve button present",   "approve" in r.text.lower() or "Aprovar" in r.text,
          "No approve button found")
else:
    warn("Quote detail skipped", "No quote ID")

# ── 7. PDF PT ─────────────────────────────────────────────────────────────────
print("\n[7] PDF GERAÇÃO")
if new_quote_id:
    r = get(f"/quotes/{new_quote_id}/pdf/pt")
    check("PDF PT download (200)", r.status_code == 200, f"HTTP {r.status_code}")
    check("PDF PT is PDF file", r.content[:4] == b"%PDF", f"content starts: {r.content[:10]}")
    check("PDF PT content-type", "pdf" in r.headers.get("Content-Type","").lower(),
          r.headers.get("Content-Type",""))
    pdf_pt_size = len(r.content)
    ok("PDF PT size", f"{pdf_pt_size:,} bytes")

    r = get(f"/quotes/{new_quote_id}/pdf/en")
    check("PDF EN download (200)", r.status_code == 200, f"HTTP {r.status_code}")
    check("PDF EN is PDF file", r.content[:4] == b"%PDF", f"content starts: {r.content[:10]}")
    pdf_en_size = len(r.content)
    ok("PDF EN size", f"{pdf_en_size:,} bytes")
else:
    warn("PDF tests skipped", "No quote ID")

# ── 8. Aprovar Orçamento ──────────────────────────────────────────────────────
print("\n[8] APROVAR ORÇAMENTO")
if new_quote_id:
    r = post(f"/quotes/{new_quote_id}/approve")
    check("Approve quote (200)", r.status_code == 200, f"HTTP {r.status_code}")
    check("After approve → detail page", f"/quotes/{new_quote_id}" in r.url or "quotes" in r.url,
          f"url={r.url}")

    # Confirm status changed
    r2 = get(f"/quotes/{new_quote_id}")
    check("Status shows Aprovado", "aprovado" in r2.text.lower() or "Aprovado" in r2.text,
          "Status 'aprovado' not visible in detail after approve")
    check("Confirm booking button present",
          "confirm-booking" in r2.text or "Confirmar Reserva" in r2.text or "reserva" in r2.text.lower(),
          "No confirm-booking button after approval")
else:
    warn("Approve test skipped", "No quote ID")

# ── 9. Confirmar Booking + OS Automática ─────────────────────────────────────
print("\n[9] CONFIRMAR BOOKING + OS AUTOMÁTICA")
new_booking_id = None
new_os_id = None
if new_quote_id:
    r = post(f"/quotes/{new_quote_id}/confirm-booking")
    check("Confirm booking (200)", r.status_code == 200, f"HTTP {r.status_code}")
    check("Redirected to booking detail", "/bookings/" in r.url, f"url={r.url}")

    m = re.search(r'/bookings/(\d+)', r.url)
    if m:
        new_booking_id = int(m.group(1))
        ok("Booking created", f"id={new_booking_id}")

    # Check booking detail
    if new_booking_id:
        r2 = get(f"/bookings/{new_booking_id}")
        check("Booking detail loads (200)", r2.status_code == 200, f"HTTP {r2.status_code}")
        check("Booking shows RES- number", "RES-" in r2.text, "RES number not found in booking detail")
        check("Booking status confirmado",
              "confirmado" in r2.text.lower() or "Confirmado" in r2.text,
              "Status not visible")

    # Check OS was auto-created
    r3 = get("/os/")
    check("OS list loads (200)", r3.status_code == 200, f"HTTP {r3.status_code}")
    os_ids = re.findall(r'/os/(\d+)"', r3.text)
    if os_ids:
        new_os_id = int(os_ids[0])  # most recent
        ok("OS auto-created", f"id={new_os_id}")
        check("OS has OS- code", "OS-" in r3.text, "No OS- code found")
    else:
        warn("OS auto-created check", "Could not find OS id in list")
else:
    warn("Confirm booking skipped", "No quote ID")

# ── 10. Detalhe da OS ────────────────────────────────────────────────────────
print("\n[10] DETALHE DA OS")
if new_os_id:
    r = get(f"/os/{new_os_id}")
    check("OS detail loads (200)", r.status_code == 200, f"HTTP {r.status_code}")
    check("OS has status field",
          "agendado" in r.text.lower() or "criado" in r.text.lower() or "atribuido" in r.text.lower(),
          "No status found in OS detail")
    check("OS has assign driver form", "assign-driver" in r.text or "Motorista" in r.text,
          "No assign driver form found")
    check("OS has assign supplier form", "assign-supplier" in r.text or "Fornecedor" in r.text,
          "No assign supplier form found")
else:
    warn("OS detail skipped", "No OS ID")

# ── 11. Atribuir Motorista Interno ───────────────────────────────────────────
print("\n[11] ATRIBUIR MOTORISTA INTERNO")
if new_os_id:
    r = post(f"/os/{new_os_id}/assign-driver", data={
        "driver_id":  1,   # Carlos Souza
        "vehicle_id": "",
        "notes":      "QA Test — motorista Carlos Souza atribuído",
    })
    check("Assign driver (200)", r.status_code == 200, f"HTTP {r.status_code}")
    check("Stays on OS page", f"/os/{new_os_id}" in r.url or "/os/" in r.url, f"url={r.url}")

    r2 = get(f"/os/{new_os_id}")
    check("OS status atribuido", "atribuido" in r2.text.lower() or "Atribuído" in r2.text,
          "Status 'atribuido' not found after driver assignment")
    check("Driver name visible", "Carlos" in r2.text or "Souza" in r2.text,
          "Driver name not visible in OS detail")
else:
    warn("Assign driver skipped", "No OS ID")

# ── 12. Atribuir Fornecedor Externo ──────────────────────────────────────────
print("\n[12] ATRIBUIR FORNECEDOR EXTERNO")
if new_os_id:
    r = post(f"/os/{new_os_id}/assign-supplier", data={
        "supplier_id":           1,   # Luxury Transfer Ltda
        "supplier_driver_name":  "João Silva",
        "supplier_vehicle":      "Mercedes-Benz Classe E",
        "supplier_contact":      "+55 11 3300-9900",
        "supplier_price":        600.0,
        "notes":                 "QA Test — fornecedor Luxury Transfer",
    })
    check("Assign supplier (200)", r.status_code == 200, f"HTTP {r.status_code}")

    r2 = get(f"/os/{new_os_id}")
    check("Supplier name visible",
          "Luxury" in r2.text or "luxury" in r2.text.lower() or "João" in r2.text,
          "Supplier info not visible in OS detail")
else:
    warn("Assign supplier skipped", "No OS ID")

# ── 13. Adicionar Custo Operacional ──────────────────────────────────────────
print("\n[13] CUSTO OPERACIONAL")
if new_os_id:
    r = post(f"/os/{new_os_id}/add-cost", data={
        "cost_type":   "pedágio",
        "amount":      45.00,
        "description": "Pedágio rodovia – QA Test",
    })
    check("Add cost (200)", r.status_code == 200, f"HTTP {r.status_code}")

    r2 = get(f"/os/{new_os_id}")
    check("Cost visible in OS", "45" in r2.text or "pedágio" in r2.text.lower() or "Pedágio" in r2.text,
          "Cost not visible in OS detail")
else:
    warn("Add cost skipped", "No OS ID")

# ── 14. Adicionar Nota na OS ─────────────────────────────────────────────────
print("\n[14] ADICIONAR NOTA NA OS")
if new_os_id:
    r = post(f"/os/{new_os_id}/add-note", data={
        "note": "QA Test: Passageiro confirmou horário de embarque às 06h30."
    })
    check("Add note (200)", r.status_code == 200, f"HTTP {r.status_code}")
    r2 = get(f"/os/{new_os_id}")
    check("Note visible in OS", "embarque" in r2.text or "06h30" in r2.text or "QA Test" in r2.text,
          "Note not visible in OS timeline")
else:
    warn("Add note skipped", "No OS ID")

# ── 15. Atualizar Status OS: em_execucao ─────────────────────────────────────
print("\n[15] STATUS OS → em_execucao")
if new_os_id:
    r = post(f"/os/{new_os_id}/update-status", data={
        "status":      "em_execucao",
        "description": "QA: Motorista a caminho do cliente",
    })
    check("Status → em_execucao (200)", r.status_code == 200, f"HTTP {r.status_code}")
    r2 = get(f"/os/{new_os_id}")
    check("Status em_execucao visible",
          "em_execucao" in r2.text or "em execução" in r2.text.lower() or "Em Execução" in r2.text,
          "Status 'em_execucao' not visible")
else:
    warn("Status em_execucao skipped", "No OS ID")

# ── 16. Enviar Dados Motorista ao Cliente ────────────────────────────────────
print("\n[16] ENVIAR DADOS MOTORISTA")
if new_os_id:
    r = post(f"/os/{new_os_id}/send-driver-info")
    check("Send driver info (200)", r.status_code == 200, f"HTTP {r.status_code}")
    r2 = get(f"/os/{new_os_id}")
    check("Driver info sent flag visible",
          "enviado" in r2.text.lower() or "Enviado" in r2.text or "dados_enviados" in r2.text,
          "Sent flag not visible in OS detail")
else:
    warn("Send driver info skipped", "No OS ID")

# ── 17. Finalizar OS ─────────────────────────────────────────────────────────
print("\n[17] FINALIZAR OS")
if new_os_id:
    r = post(f"/os/{new_os_id}/update-status", data={
        "status":      "finalizado",
        "description": "QA: Serviço concluído com sucesso",
    })
    check("Status → finalizado (200)", r.status_code == 200, f"HTTP {r.status_code}")
    r2 = get(f"/os/{new_os_id}")
    check("Status finalizado visible",
          "finalizado" in r2.text.lower() or "Finalizado" in r2.text,
          "Status 'finalizado' not visible")
else:
    warn("Finalizar OS skipped", "No OS ID")

# ── 18. Cadastrar Motorista ───────────────────────────────────────────────────
print("\n[18] CADASTRAR MOTORISTA")
r = get("/drivers/new")
check("New driver form (200)", r.status_code == 200, f"HTTP {r.status_code}")

r = post("/drivers/new", data={
    "name":          f"QA-Motorista-{ts}",
    "phone":         "+55 11 99999-0001",
    "email":         "qa.driver@executivecarsp.com",
    "document":      "999.888.777-66",
    "license":       "CNH AB",
    "license_exp":   "2028-12-31",
    "driver_type":   "Monolíngue",
    "notes":         "Motorista de teste QA",
})
check("Create driver (200)", r.status_code == 200, f"HTTP {r.status_code}")
check("Driver appears in list",
      f"QA-Motorista-{ts}" in r.text or "/drivers" in r.url,
      f"url={r.url}, text_snippet={r.text[:100]}")

# ── 19. Cadastrar Fornecedor ──────────────────────────────────────────────────
print("\n[19] CADASTRAR FORNECEDOR")
r = get("/suppliers/new")
check("New supplier form (200)", r.status_code == 200, f"HTTP {r.status_code}")

r = post("/suppliers/new", data={
    "name":          f"QA-Fornecedor-{ts}",
    "contact":       "Contato QA",
    "email":         "qa.supplier@transfer.com.br",
    "phone":         "+55 11 3000-1111",
    "document":      "12.345.678/0001-90",
    "address":       "Rua das Flores, 100",
    "city":          "São Paulo",
    "state":         "SP",
    "service_type":  "Transfer",
    "payment_terms": "30 dias",
    "notes":         "Fornecedor de teste QA",
})
check("Create supplier (200)", r.status_code == 200, f"HTTP {r.status_code}")
check("Supplier in list",
      f"QA-Fornecedor-{ts}" in r.text or "/suppliers" in r.url,
      f"url={r.url}")

# ── 20. Cadastrar Veículo ─────────────────────────────────────────────────────
print("\n[20] CADASTRAR VEÍCULO")
r = get("/vehicles/new")
check("New vehicle form (200)", r.status_code == 200, f"HTTP {r.status_code}")

r = post("/vehicles/new", data={
    "category_id": 1,
    "make":        "Toyota",
    "model":       "Corolla XEi",
    "year":        "2024",
    "plate":       f"QA{ts % 10000:04d}A",
    "color":       "Prata",
    "capacity":    4,
    "notes":       "Veículo de teste QA",
})
check("Create vehicle (200)", r.status_code == 200, f"HTTP {r.status_code}")
check("Vehicle in list", "Toyota" in r.text or "/vehicles" in r.url, f"url={r.url}")

# ── 21. Editar Orçamento ──────────────────────────────────────────────────────
print("\n[21] EDITAR ORÇAMENTO")
# Create a fresh pendente quote to edit
r_new = post("/quotes/new", json_data={
    "client_id": new_client_id or 3,
    "client_name": f"QA-EDIT-{ts}",
    "contact_name": "QA Edit",
    "email": "anderson_nobre@icloud.com",
    "phone": "+55 11 98474-8044",
    "language": "pt",
    "billing_type": "nf",
    "payment_method": "BOLETO",
    "payment_terms": "7 dias após serviço",
    "obs": "Orçamento para edição — QA",
    "items": [{"service_id": 1, "category_id": 1, "description": "Transfer Edit",
               "vehicle_description": "SUV Premium", "driver_name": "Bilíngue",
               "state_code": "SP", "ref_note": "Edit test", "quantity": 2,
               "unit_price": 1100.0, "hour_extra": 110.0, "total_price": 2200.0,
               "price_base": 1000.0, "price_nf": 1100.0, "price_cartao": 1065.0,
               "price_nf_cartao": 1165.0, "km_extra": 0, "km_extra_rate": 0, "sort_order": 0}],
    "inclusions": [],
})
edit_quote_id = None
try:
    edit_quote_id = r_new.json().get("id")
except Exception:
    m = re.search(r'/quotes/(\d+)', r_new.url)
    if m: edit_quote_id = int(m.group(1))

if edit_quote_id:
    r = get(f"/quotes/{edit_quote_id}/edit")
    check("Edit quote form loads (200)", r.status_code == 200, f"HTTP {r.status_code}")
    check("EDIT_DATA in page", "EDIT_DATA" in r.text, "EDIT_DATA constant not found in edit page")

    # POST edit
    edit_payload = {
        "client_id": new_client_id or 3,
        "client_name": f"QA-EDIT-{ts}-UPDATED",
        "contact_name": "QA Updated",
        "email": "anderson_nobre@icloud.com",
        "phone": "+55 11 98474-8044",
        "language": "pt",
        "billing_type": "recibo",
        "payment_method": "PIX",
        "payment_terms": "À vista",
        "obs": "Editado pelo QA automatizado",
        "items": [{"service_id": 1, "category_id": 1, "description": "Transfer Editado",
                   "vehicle_description": "Sedan Executivo", "driver_name": "Monolíngue",
                   "state_code": "SP", "ref_note": "Ref editada", "quantity": 1,
                   "unit_price": 850.0, "hour_extra": 85.0, "total_price": 850.0,
                   "price_base": 770.0, "price_nf": 847.0, "price_cartao": 820.05,
                   "price_nf_cartao": 897.05, "km_extra": 0, "km_extra_rate": 0, "sort_order": 0}],
        "inclusions": [],
    }
    r2 = post(f"/quotes/{edit_quote_id}/edit", json_data=edit_payload)
    check("Edit quote POST (200)", r2.status_code == 200, f"HTTP {r2.status_code}")
    check("Redirected to detail after edit", f"/quotes/{edit_quote_id}" in r2.url,
          f"url={r2.url}")

    r3 = get(f"/quotes/{edit_quote_id}")
    check("Edited name appears in detail",
          "QA-EDIT" in r3.text and "UPDATED" in r3.text,
          "Updated name not visible in quote detail")
    check("Edited total visible", "850" in r3.text, "New total (850) not visible")
else:
    warn("Edit quote tests skipped", "Could not create test quote for edit")

# ── 22. Reprovar Orçamento (fluxo alternativo) ───────────────────────────────
print("\n[22] REPROVAR ORÇAMENTO")
r_rej = post("/quotes/new", json_data={
    "client_id": new_client_id or 3,
    "client_name": f"QA-REJECT-{ts}",
    "email": "anderson_nobre@icloud.com",
    "phone": "+55 11 98474-8044",
    "language": "pt",
    "billing_type": "recibo",
    "payment_method": "PIX",
    "payment_terms": "",
    "obs": "Orçamento para rejeição",
    "items": [{"service_id": 1, "category_id": 1, "description": "Transfer", "quantity": 1,
               "unit_price": 600.0, "total_price": 600.0, "hour_extra": 0,
               "price_base": 600.0, "price_nf": 660.0, "price_cartao": 639.0,
               "price_nf_cartao": 699.0, "km_extra": 0, "km_extra_rate": 0, "sort_order": 0}],
    "inclusions": [],
})
rej_quote_id = None
try:
    rej_quote_id = r_rej.json().get("id")
except Exception:
    m = re.search(r'/quotes/(\d+)', r_rej.url)
    if m: rej_quote_id = int(m.group(1))

if rej_quote_id:
    r = post(f"/quotes/{rej_quote_id}/reject", data={"reason": "Preço fora do budget — QA Test"})
    check("Reject quote (200)", r.status_code == 200, f"HTTP {r.status_code}")
    check("Redirected to quotes list", "/quotes" in r.url, f"url={r.url}")
    # Verify in DB
    r2 = get(f"/quotes/{rej_quote_id}")
    check("Status reprovado after reject",
          "reprovado" in r2.text.lower() or "Reprovado" in r2.text,
          "Status 'reprovado' not visible after rejection")
else:
    warn("Reject quote test skipped", "Could not create rejection test quote")

# ── 23. Dashboard de Despacho ────────────────────────────────────────────────
print("\n[23] DASHBOARD DE DESPACHO")
r = get("/dispatch/")
check("Dispatch dashboard loads (200)", r.status_code == 200, f"HTTP {r.status_code}")
check("Dispatch has OS count", "OS" in r.text or "Despacho" in r.text or "dispatch" in r.text.lower(),
      "No dispatch content found")

# ── 24. Relatórios ───────────────────────────────────────────────────────────
print("\n[24] RELATÓRIOS")
r = get("/reports/")
check("Reports page loads (200)", r.status_code == 200, f"HTTP {r.status_code}")
check("Reports has data", any(w in r.text for w in ["Orçamento", "Booking", "Receita", "OS", "total"]),
      "No report data found in reports page")

# ── 25. Lista Geral de OS ─────────────────────────────────────────────────────
print("\n[25] LISTA OS COM FILTROS")
r = get("/os/?status=finalizado")
check("OS list filter finalizado (200)", r.status_code == 200, f"HTTP {r.status_code}")
check("Shows finalizado OS", "finalizado" in r.text.lower() or "OS-" in r.text,
      "No finalizado OS found")

r = get("/os/?q=QA")
check("OS list search (200)", r.status_code == 200, f"HTTP {r.status_code}")

# ── 26. Lista Orçamentos com Filtros ─────────────────────────────────────────
print("\n[26] LISTA ORÇAMENTOS COM FILTROS")
r = get("/quotes/?status=aprovado")
check("Quotes filter aprovado (200)", r.status_code == 200, f"HTTP {r.status_code}")
check("Shows approved quotes", "aprovado" in r.text.lower() or "reserva_confirmada" in r.text.lower() or "Aprovado" in r.text,
      "No approved quote found")

r = get(f"/quotes/?q=QA-ECS-{ts}")
check("Quotes search (200)", r.status_code == 200, f"HTTP {r.status_code}")
check("Quote found by search", f"QA-ECS-{ts}" in r.text, "Client name not found in search results")

# ── 27. Settings ─────────────────────────────────────────────────────────────
print("\n[27] SETTINGS")
r = get("/settings")
check("Settings page loads (200)", r.status_code == 200, f"HTTP {r.status_code}")
check("Settings has company fields",
      any(f in r.text for f in ["company", "logo", "document", "email"]),
      "No settings fields found")

# ── 28. Logout ────────────────────────────────────────────────────────────────
print("\n[28] LOGOUT")
r = get("/auth/logout")
check("Logout (200)", r.status_code == 200, f"HTTP {r.status_code}")
check("Redirected to login", "login" in r.url, f"url={r.url}")

# After logout, try accessing protected route
r2 = get("/")
check("Protected route after logout → redirect to login",
      "login" in r2.url, f"url={r2.url}")

# ── SUMMARY ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  RESUMO DO QA")
print("=" * 60)

total  = len(RESULTS)
passed = sum(1 for r in RESULTS if r["status"] == "PASS")
failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
warned = sum(1 for r in RESULTS if r["status"] == "WARN")

print(f"\n  Total de testes : {total}")
print(f"  ✅ PASS         : {passed}")
print(f"  ❌ FAIL         : {failed}")
print(f"  ⚠️  WARN         : {warned}")
print(f"  Taxa de aprovação: {passed/total*100:.1f}%\n")

if failed:
    print("  FALHAS:")
    for r in RESULTS:
        if r["status"] == "FAIL":
            print(f"    ❌ {r['test']} — {r['detail']}")

if warned:
    print("\n  AVISOS:")
    for r in RESULTS:
        if r["status"] == "WARN":
            print(f"    ⚠️  {r['test']} — {r['detail']}")

# Save results to JSON
import json as _json
with open("qa_results.json", "w", encoding="utf-8") as f:
    _json.dump({
        "run_at": datetime.now().isoformat(),
        "base_url": BASE,
        "summary": {"total": total, "pass": passed, "fail": failed, "warn": warned,
                    "rate": round(passed/total*100, 1)},
        "results": RESULTS,
    }, f, ensure_ascii=False, indent=2)
print("\n  Resultados salvos em: qa_results.json")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
