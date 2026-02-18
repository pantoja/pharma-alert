import time
from app.config import Config
from app.database import Database
from app.notifier import Notifier
from app.scraper import PagueMenosScraper, DrogasilScraper, DrogariaSaoPauloScraper

def main():
    config_data = Config.load_products()
    products = config_data.get("products", [])
    
    db = Database()
    scrapers = [
        PagueMenosScraper(),
        DrogasilScraper(),
        DrogariaSaoPauloScraper()
    ]
    
    cep = config_data.get("cep")
    
    for product in products:
        name = product["name"]
        search_term = product["search_term"]
        required_terms = product.get("required_terms", [])
        threshold = product["threshold_price"]
        
        print(f"\nBuscando: {name} ({search_term})")
        print(f"  -> Alvo por Caixa: R$ {threshold:.2f}")
        if cep:
            print(f"  -> CEP: {cep}")
        
        all_results = []
        
        for scraper in scrapers:
            pharmacy_name = scraper.__class__.__name__.replace("Scraper", "")
            print(f"  Pesquisando em {pharmacy_name}...")
            
            try:
                # Passa o CEP para os scrapers
                results = scraper.search_medication(search_term, cep=cep)
                
                for res in results:
                    # Aplicar filtros (ex: "2mg")
                    title_upper = res["title"].upper()
                    if all(term.upper() in title_upper for term in required_terms):
                        # Cálculo do Preço Unitário Efetivo: (Preço + Frete) / Quantidade
                        res["total_effective_unit"] = (res["price"] + res["shipping"]) / res["quantity"]
                        all_results.append(res)
            except Exception as e:
                print(f"    Erro ao processar {pharmacy_name}: {e}")
            
            time.sleep(2)
        
        if not all_results:
            print("  Nenhum resultado encontrado com os filtros aplicados.")
            continue
            
        # Encontrar a melhor oferta (menor unit_price_efetivo para comparar caixas de tamanhos diferentes)
        best_offer = min(all_results, key=lambda x: x["total_effective_unit"])
        
        total_price_with_shipping = best_offer['price'] + best_offer['shipping']
        
        print(f"  Melhor oferta encontrada: {best_offer['title']}")
        print(f"  Preço Final da Caixa (c/ Frete): R$ {total_price_with_shipping:.2f} | Farmácia: {best_offer['pharmacy']}")
        
        # Salvar TODOS os resultados filtrados no banco, marcando o vencedor
        for res in all_results:
            is_winner = (res == best_offer)
            db.save_price(
                pharmacy=res["pharmacy"],
                product_name=res["title"],
                unit_price=res["unit_price"], # Preço unitário puro (sem frete)
                total_price=res["price"],     # Preço total da caixa
                shipping_cost=res["shipping"],
                total_effective_price=res["total_effective_unit"], # Preço unitário com frete proporcional
                is_kit=(res["quantity"] > 1),
                kit_size=res["quantity"],
                is_best_offer=is_winner
            )

        if total_price_with_shipping < threshold:
            Notifier.send_alert(
                product_name=best_offer["title"],
                pharmacy=best_offer["pharmacy"],
                price=total_price_with_shipping, # Valor total da caixa
                url=best_offer["url"]
            )

if __name__ == "__main__":
    main()
