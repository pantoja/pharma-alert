from scrapling import Fetcher
import json
import re
import httpx
from selectolax.parser import HTMLParser

class BaseScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        # Fetcher uses curl-cffi for stealth without needing Playwright binary
        self.fetcher = Fetcher()

    def fetch_page(self, url):
        try:
            # Scrapling Fetcher automatically handles headers and anti-bot measures via curl-cffi
            response = self.fetcher.get(url)
            if response.status == 200:
                return response.body.decode('utf-8', 'ignore') if hasattr(response, 'body') else ""
            else:
                print(f"Erro ao acessar {url}: Status {response.status}")
                # Tentamos um fallback com httpx se o SteathFetcher falhar por algum motivo
                with httpx.Client(headers=self.headers, follow_redirects=True, timeout=15.0) as client:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        return resp.text
                return None
        except Exception as e:
            print(f"Erro ao acessar {url}: {e}")
            return None

    def parse_price(self, price_str):
        if not price_str: return 0.0
        # Remove R$, dots, and replace comma with dot
        clean = re.sub(r'[^\d,]', '', price_str).replace(',', '.')
        try:
            return float(clean) if clean else 0.0
        except:
            return 0.0

    def parse_quantity(self, title):
        if not title: return 1
        # Procura padrões como "30 comprimidos", "28 drágeas", "60 caps"
        match = re.search(r'(\d+)\s*(comprimidos|caps|drag|unid|comp|drágeas|cápsulas)', title, re.IGNORECASE)
        if match:
            return int(match.group(1))
        # Fallback: procurar qualquer número isolado que pareça uma contagem comum
        match = re.search(r'\b(20|21|28|30|42|56|60|84|90)\b', title)
        return int(match.group(1)) if match else 1

    def calculate_best_unit_price(self, base_price, teasers, available_qty):
        """
        Calcula o melhor preço unitário considerando promoções progressivas (ex: Leve 3 Pague 2).
        Retorna (preço_unitário_calculado, info_promoção)
        """
        best_price = float(base_price)
        promo_info = ""

        if not teasers:
            return best_price, promo_info

        for teaser in teasers:
            try:
                conditions = teaser.get("conditions", {})
                min_qty = int(conditions.get("minimumQuantity", 1))
                
                # Só aplica se houver estoque suficiente para a promoção
                if min_qty > 1 and available_qty >= min_qty:
                    effects = teaser.get("effects", {})
                    params = effects.get("parameters", [])
                    
                    discount_pct = 0
                    for p in params:
                        if p.get("name") == "PercentualDiscount":
                            discount_pct = float(p.get("value", 0))
                    
                    if discount_pct > 0:
                        # Lógica VTEX comum: "Leve X, o último sai com Y% de desconto"
                        # Para "Leve 3 Pague 2", o desconto é 100% em 1 item a cada 3.
                        total_cost = (base_price * (min_qty - (discount_pct / 100.0)))
                        promo_unit_price = total_cost / min_qty
                        
                        if promo_unit_price < best_price:
                            best_price = promo_unit_price
                            promo_info = f"Leve {min_qty} Pague {(min_qty - (discount_pct/100.0)):.0f}"
                            if discount_pct < 100:
                                promo_info = f"Leve {min_qty} com {discount_pct}% no último"
            except Exception as e:
                print(f"    Erro ao processar teaser: {e}")
                continue
                
        return best_price, promo_info

class DrogasilScraper(BaseScraper):
    def search_medication(self, term, cep=None):
        base_url = "https://www.drogasil.com.br"
        url = f"{base_url}/search?w={term}"
        print(f"    Buscando Drogasil via Scrapling: {url}")
        html = self.fetch_page(url)
        if not html: return []
        parser = HTMLParser(html)
        next_data_script = parser.css_first("script#__NEXT_DATA__")
        results = []
        
        if next_data_script:
            try:
                data = json.loads(next_data_script.text())
                def find_products(obj):
                    if isinstance(obj, dict):
                        if "products" in obj and isinstance(obj["products"], list):
                            return obj["products"]
                        for v in obj.values():
                            res = find_products(v)
                            if res: return res
                    elif isinstance(obj, list):
                        for item in obj:
                            res = find_products(item)
                            if res: return res
                    return None
                
                raw_products = find_products(data) or []
                for prod in raw_products:
                    title = prod.get("name")
                    # Tenta várias possibilidades de preço no JSON da Drogasil
                    price = prod.get("price", {}).get("value")
                    if not price:
                        price = prod.get("price", {}).get("final_price", {}).get("value")
                    if not price:
                        price = prod.get("priceService")
                    if not price:
                        price = prod.get("valueTo", 0)
                    
                    link = base_url + "/" + prod.get("url_key", prod.get("url", ""))
                    if not link.startswith("http"): link = base_url + link
                    
                    # Fix: Busca o preço real na página do produto (PDP)
                    real_price = self.fetch_pdp_price(link)
                    if real_price > 0:
                        price = real_price
                    
                    qty = self.parse_quantity(title)
                    # Detecta promoções (Leve Mais Pague Menos)
                    price_aux = prod.get("price_aux", {})
                    lmpm_price = price_aux.get("lmpm_value_to")
                    lmpm_qty = price_aux.get("lmpm_qty")
                    
                    display_title = title
                    if lmpm_price and lmpm_qty:
                        # Se o preço promocional for menor, usamos ele
                        if float(lmpm_price) < price:
                            price = float(lmpm_price)
                            display_title += f" (Leve {lmpm_qty} Pague Menos: R$ {lmpm_price} cada)"

                    sku = prod.get("sku", prod.get("objectID"))
                    shipping_cost = self.fetch_shipping_cost(sku, cep)
                    
                    results.append({
                        "pharmacy": "Drogasil",
                        "title": display_title,
                        "price": float(price),
                        "quantity": qty,
                        "unit_price": float(price) / qty if qty > 0 else float(price),
                        "url": link,
                        "shipping": shipping_cost
                    })
            except Exception as e:
                print(f"    Erro no parse JSON Drogasil: {e}")
        
        # Fallback CSS se JSON vier vazio
        if not results:
            # Classes da Drogasil costumam mudar, mas o h2 costuma ser o título
            cards = parser.css("div[class*='ProductCard']")
            for card in cards:
                title_elem = card.css_first("h2")
                price_elem = card.css_first("span[class*='Price']")
                link_elem = card.css_first("a")
                if title_elem and price_elem:
                    title = title_elem.text(strip=True)
                    price = self.parse_price(price_elem.text())
                    link = base_url + link_elem.attributes.get("href", "")
                    qty = self.parse_quantity(title)
                    # Fallback também deve ser validado no PDP ou checar texto
                    real_pdp_price = self.fetch_pdp_price(link)
                    if real_pdp_price > 0:
                        results.append({
                            "pharmacy": "Drogasil",
                            "title": title,
                            "price": real_pdp_price,
                            "quantity": qty,
                            "unit_price": real_pdp_price / qty if qty > 0 else real_pdp_price,
                            "url": link,
                            "shipping": 0.0 # Shipping check here might be too heavy for fallback
                        })
        return results

    def fetch_pdp_price(self, url):
        """Busca o preço com desconto (value_to) na página de detalhes do produto."""
        try:
            html = self.fetch_page(url)
            if not html: return 0.0
            
            parser = HTMLParser(html)
            next_data_script = parser.css_first("script#__NEXT_DATA__")
            if next_data_script:
                data = json.loads(next_data_script.text())
                
                def find_field(obj, field_name):
                    if isinstance(obj, dict):
                        if field_name in obj: return obj[field_name]
                        for v in obj.values():
                            res = find_field(v, field_name)
                            if res: return res
                    elif isinstance(obj, list):
                        for item in obj:
                            res = find_field(item, field_name)
                            if res: return res
                    return None

                # Tenta value_to (preço final com desconto)
                # Se estiver esgotado, value_to costuma ser None ou 0
                value_to = find_field(data, "value_to")
                
                # Verifica se há indicador de estoque
                stock_status = find_field(data, "status") # IN_STOCK ou similar
                if stock_status and stock_status != "IN_STOCK" and stock_status != 1:
                    return 0.0

                # Tenta lmpm (Leve Mais Pague Menos)
                price_aux = find_field(data, "price_aux")
                if price_aux:
                    lmpm_price = price_aux.get("lmpm_value_to")
                    if lmpm_price: return float(lmpm_price)

                if value_to: return float(value_to)
                
                # Fallback: priceService se estiver no PDP (as vezes tem)
                ps = find_field(data, "priceService")
                if ps: return float(ps)
                
            # Verifica visualmente se está esgotado no HTML
            if "Produto Indisponível" in html or "Avise-me" in html:
                return 0.0
                
            return 0.0
        except:
            return 0.0

    def fetch_shipping_cost(self, sku, cep):
        """Busca o frete na API da Drogasil."""
        if not cep or not sku: return 0.0
        # Normaliza CEP
        cep_clean = cep.replace("-", "")
        url = "https://www.drogasil.com.br/api/v1/shipping/calculate"
        payload = {
            "items": [{"sku": str(sku), "quantity": 1}],
            "zipCode": cep_clean
        }
        try:
            headers = self.headers.copy()
            headers["Content-Type"] = "application/json"
            # Adiciona referer para evitar 503/403 em algumas chamadas de API
            headers["Referer"] = "https://www.drogasil.com.br/"
            
            resp = self.fetcher.post(url, data=json.dumps(payload), headers=headers)
            if resp.status in [200, 206]:
                data = json.loads(resp.body)
                options = data.get("deliveryOptions", [])
                if options:
                    prices = [float(opt.get("price", 999)) for opt in options]
                    return min(prices) if prices else 0.0
            elif resp.status == 503:
                # Se der 503, tentamos uma vez mais sem o hífen no CEP (já feito acima) ou com headers mínimos
                pass
        except Exception as e:
            print(f"    Erro ao calcular frete Drogasil: {e}")
        return 0.0

class PagueMenosScraper(BaseScraper):
    def search_medication(self, term, cep=None):
        # Mudando para Intelligent Search para capturar promoções (teasers)
        api_url = f"https://www.paguemenos.com.br/api/io/_v/api/intelligent-search/product_search/trade-policy/1?query={term}&count=12"
        print(f"    Buscando Pague Menos via Intelligent Search: {api_url}")
        
        results = []
        try:
            resp = self.fetcher.get(api_url)
            if resp.status in [200, 206]:
                data = json.loads(resp.body)
                for prod in data.get("products", []):
                    title = prod.get("productName")
                    items = prod.get("items", [])
                    if items:
                        item = items[0]
                        sellers = item.get("sellers", [])
                        if sellers:
                            offer = sellers[0].get("commertialOffer", {})
                            available_qty = offer.get("AvailableQuantity", 0)
                            
                            if available_qty > 0:
                                base_price = float(offer.get("Price", 0))
                                if base_price > 0:
                                    # Detecta promoções (ex: Leve 3 Pague 2)
                                    teasers = offer.get("teasers", [])
                                    price, promo_info = self.calculate_best_unit_price(base_price, teasers, available_qty)
                                    
                                    display_title = title
                                    if promo_info:
                                        display_title += f" ({promo_info})"

                                    link = "https://www.paguemenos.com.br" + prod.get("link", "")
                                    qty = self.parse_quantity(title)
                                    
                                    shipping_cost = 0.0
                                    sku = item.get("itemId")
                                    if cep and sku:
                                        shipping_cost = self.fetch_shipping_cost(sku, cep)
                                    
                                    results.append({
                                        "pharmacy": "Pague Menos",
                                        "title": display_title,
                                        "price": price,
                                        "quantity": qty,
                                        "unit_price": price / qty if qty > 0 else price,
                                        "url": link,
                                        "shipping": shipping_cost
                                    })
        except Exception as e:
            print(f"    Erro ao consultar API Pague Menos: {e}")
            
        # Fallback LEGACY (LD+JSON) se API falhar ou não trouxer nada
        if not results:
            # ... mantém a lógica anterior se desejar, mas vou simplificar para carregar do HTML se precisar
            url = f"https://www.paguemenos.com.br/search?_q={term}"
            html = self.fetch_page(url)
            if html:
                parser = HTMLParser(html)
                scripts = parser.css("script[type='application/ld+json']")
                for script in scripts:
                    try:
                        data = json.loads(script.text())
                        if data.get("@type") == "ItemList" and "itemListElement" in data:
                            for item in data["itemListElement"]:
                                prod = item.get("item", {})
                                if prod.get("@type") == "Product":
                                    offers = prod.get("offers", {})
                                    availability = offers.get("availability")
                                    # FILTRO DE ESTOQUE LD+JSON
                                    if availability == "https://schema.org/InStock":
                                        title = prod.get("name")
                                        price = offers.get("lowPrice") or offers.get("price", 0)
                                        link = prod.get("url")
                                        qty = self.parse_quantity(title)
                                        results.append({
                                            "pharmacy": "Pague Menos",
                                            "title": title,
                                            "price": float(price),
                                            "quantity": qty,
                                            "unit_price": float(price) / qty if qty > 0 else float(price),
                                            "url": link,
                                            "shipping": 0.0
                                        })
                    except: continue
        return results

    def fetch_shipping_cost(self, sku, cep):
        """Simulação de frete VTEX para Pague Menos."""
        if not cep or not sku: return 0.0
        url = "https://www.paguemenos.com.br/api/checkout/pub/orderForms/simulation"
        payload = {
            "items": [{"id": str(sku), "quantity": 1, "seller": "1"}],
            "country": "BRA",
            "postalCode": cep.replace("-", ""),
            "shippingData": {
                "address": {
                    "postalCode": cep.replace("-", ""),
                    "country": "BRA"
                }
            }
        }
        try:
            headers = self.headers.copy()
            headers["Content-Type"] = "application/json"
            # Define o cookie de CEP para tentar "forçar" o contexto regional na VTEX
            headers["Cookie"] = f"vtex_postalCode={cep.replace('-', '')};"
            
            resp = self.fetcher.post(url, data=json.dumps(payload), headers=headers)
            if resp.status in [200, 206]:
                data = json.loads(resp.body)
                logistics = data.get("shippingData", {}).get("logisticsInfo", [])
                if logistics:
                    slas = logistics[0].get("slas", [])
                    if slas:
                        # FILTRO: Ignorar "Retire na Loja" (deliveryChannel != 'delivery')
                        delivery_slas = [s for s in slas if s.get("deliveryChannel") == "delivery"]
                        if delivery_slas:
                            prices = [float(s.get("price", 99999)) / 100.0 for s in delivery_slas]
                            return min(prices) if prices else 0.0
                        else:
                            # Se só houver retirada, o frete de entrega é "infinito" ou não disponível
                            return 0.0 
        except Exception as e:
            print(f"    Erro ao calcular frete Pague Menos: {e}")
        return 0.0

class DrogariaSaoPauloScraper(BaseScraper):
    def search_medication(self, term, cep=None):
        # Drogaria SP as vezes funciona via API direto
        api_url = f"https://www.drogariasaopaulo.com.br/api/io/_v/api/intelligent-search/product_search/trade-policy/1?query={term}&count=48&page=1"
        print(f"    Buscando Drogaria São Paulo via API: {api_url}")
        
        results = []
        try:
            # Usamos o fetcher para herdar os benefícios de evasão de bot
            resp = self.fetcher.get(api_url)
            if resp.status in [200, 206]:
                data = json.loads(resp.body)
                for prod in data.get("products", []):
                    title = prod.get("productName")
                    items = prod.get("items", [])
                    if items:
                        item = items[0]
                        price = 0
                        sellers = item.get("sellers", [])
                        if sellers:
                            offer = sellers[0].get("commertialOffer", {})
                            available_qty = offer.get("AvailableQuantity", 0)
                            
                            # FILTRO DE ESTOQUE
                            if available_qty > 0:
                                price = float(offer.get("Price", 0))
                                if price > 0:
                                    # Detecta promoções (teasers)
                                    teasers = offer.get("teasers", [])
                                    final_price, promo_info = self.calculate_best_unit_price(price, teasers, available_qty)
                                    
                                    display_title = title
                                    if promo_info:
                                        display_title += f" ({promo_info})"

                                    link = "https://www.drogariasaopaulo.com.br" + prod.get("link", "")
                                    qty = self.parse_quantity(title)
                                    
                                    # Calcula frete
                                    shipping_cost = 0.0
                                    sku = item.get("itemId")
                                    if cep and sku:
                                        shipping_cost = self.fetch_shipping_cost(sku, cep)
                                        
                                    results.append({
                                        "pharmacy": "Drogaria São Paulo",
                                        "title": display_title,
                                        "price": final_price,
                                        "quantity": qty,
                                        "unit_price": final_price / qty if qty > 0 else final_price,
                                        "url": link,
                                        "shipping": shipping_cost
                                    })
        except Exception as e:
            print(f"    Erro ao consultar API Drogaria SP: {e}")
            
        # Fallback HTML se API falhar
        if not results:
            url = f"https://www.drogariasaopaulo.com.br/search?_q={term}"
            html = self.fetch_page(url)
            if html:
                parser = HTMLParser(html)
                cards = parser.css(".product-item") or parser.css("[class*='product-card']")
                for card in cards:
                    title_elem = card.css_first("[class*='name']")
                    price_elem = card.css_first("[class*='price']")
                    link_elem = card.css_first("a")
                    if title_elem and price_elem:
                        title = title_elem.text(strip=True)
                        price = self.parse_price(price_elem.text())
                        link = link_elem.attributes.get("href", "")
                        if link and not link.startswith("http"):
                            link = "https://www.drogariasaopaulo.com.br" + link
                        
                        # Fallback CSS: Verificar se o card indica esgotado
                        card_html = card.html().lower()
                        if "esgotado" in card_html or "avise-me" in card_html:
                            continue

                        qty = self.parse_quantity(title)
                        results.append({
                            "pharmacy": "Drogaria São Paulo",
                            "title": title,
                            "price": price,
                            "quantity": qty,
                            "unit_price": price / qty if qty > 0 else price,
                            "url": link,
                            "shipping": 0.0 # Fallback HTML is simplified
                        })
        return results

    def fetch_shipping_cost(self, sku, cep):
        """Simulação de frete VTEX para Drogaria SP."""
        if not cep or not sku: return 0.0
        url = "https://www.drogariasaopaulo.com.br/api/checkout/pub/orderforms/simulation"
        payload = {
            "items": [{"id": str(sku), "quantity": 1, "seller": "1"}],
            "country": "BRA",
            "postalCode": cep.replace("-", ""),
            "shippingData": {
                "address": {
                    "postalCode": cep.replace("-", ""),
                    "country": "BRA"
                }
            }
        }
        try:
            headers = self.headers.copy()
            headers["Content-Type"] = "application/json"
            headers["Cookie"] = f"vtex_postalCode={cep.replace('-', '')};"
            
            resp = self.fetcher.post(url, data=json.dumps(payload), headers=headers)
            if resp.status in [200, 206]:
                data = json.loads(resp.body)
                logistics = data.get("shippingData", {}).get("logisticsInfo", [])
                if logistics:
                    slas = logistics[0].get("slas", [])
                    if slas:
                        delivery_slas = [s for s in slas if s.get("deliveryChannel") == "delivery"]
                        if delivery_slas:
                            prices = [float(s.get("price", 99999)) / 100.0 for s in delivery_slas]
                            return min(prices) if prices else 0.0
                        else:
                            return 0.0
        except Exception as e:
            print(f"    Erro ao calcular frete Drogaria SP: {e}")
        return 0.0
