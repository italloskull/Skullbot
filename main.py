import os
import sys
import requests
import traceback
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

# Configurações
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
SITE_URL = "https://online-fix.me/"
LAST_GAME_FILE = "last_game.txt"
TEST_MODE = False  # Desativado para o bot rodar normalmente na nuvem

def get_latest_games(last_known_link):
    try:
        # Usamos cabeçalhos customizados completos para simular um navegador real
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        # Usamos o requests direto para evitar o bug de quebra do cloudscraper no Cloudflare moderno
        response = requests.get(SITE_URL, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Procura por todas as tags de data/hora na página
        time_elements = soup.find_all('time', datetime=True)

        new_games = []
        if time_elements:
            # Ordena do mais recente (agora) para o mais antigo
            time_elements = sorted(time_elements, key=lambda t: t.get('datetime'), reverse=True)

            for time_element in time_elements:
                img_element = None
                current_parent = time_element.parent
                while current_parent and current_parent.name not in ['body', 'html']:
                    # Flexibiliza a busca: suporta lazy loading (data-src) e ignora a exigência da pasta exata
                    possible_img = current_parent.find('img')
                    if possible_img:
                        src = possible_img.get('data-src') or possible_img.get('src') or ""
                        if '/uploads/' in src or 'post' in src or possible_img.get('alt'):
                            img_element = possible_img
                            break
                    current_parent = current_parent.parent

                if img_element:
                    link_element = img_element.find_parent('a')
                    if link_element:
                        title = link_element.get('title') or img_element.get('alt') or link_element.text.strip()
                        link = link_element.get('href')
                        if link and link.startswith('/'):
                            link = f"https://online-fix.me{link}"

                        # Se o link bater com o último jogo que o bot lembra, ele para de procurar na hora!
                        if link == last_known_link and not TEST_MODE:
                            break

                        image_url = img_element.get('data-src') or img_element.get('src')
                        if image_url and image_url.startswith('/'):
                            image_url = f"https://online-fix.me{image_url}"

                        new_games.append({"title": title, "link": link, "image_url": image_url})

            # Inverte a lista para mandar no Discord do mais velho (primeiro que saiu) para o mais novo
            new_games.reverse()
            return new_games

    except Exception as e:
        print(f"Erro ao fazer scraping do site (possível bloqueio Cloudflare): {e}")
        traceback.print_exc()
    return []

def get_game_description(game_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    try:
        response = requests.get(game_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Tenta pegar a descrição pela tag meta (SEO ou OpenGraph) do site
        meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
        desc = ""

        # 1. Tenta extrair a sinopse original em inglês que costuma ficar na tag <i>
        for i_tag in soup.find_all('i'):
            texto_i = i_tag.text.strip()
            # Pega a primeira tag <i> que tenha um tamanho razoável (mais de 40 caracteres)
            if len(texto_i) > 40:
                desc = texto_i
                break

        # 2. Se não achou na tag <i>, tenta a âncora "Informação sobre o jogo" (em russo)
        if not desc:
            info_tag = soup.find(string=lambda text: text and "Информация о игре" in text)
            
            if info_tag:
                container = info_tag.parent
                if container.name in ['b', 'strong', 'span', 'i', 'em']:
                    container = container.parent
                
            # Pega tudo que vem após a âncora
            desc = container.text.split("Информация о игре")[-1].strip()
            desc = desc.lstrip(':- \n').strip()
            
            # Se a descrição estiver vazia, a sinopse pode estar nos próximos parágrafos
            if len(desc) < 10:
                next_node = container.find_next_sibling()
                while next_node:
                    # Para de ler ao encontrar a seção de Arquivos do Jogo
                    if "Файлы для игры" in next_node.text:
                        break
                    desc += " " + next_node.text.strip()
                    next_node = next_node.find_next_sibling()
                    
            desc = desc.split("Файлы для игры")[0].strip()

        # Fallback: se não encontrar no texto visível, tenta a tag meta
        if not desc:
            meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
            if meta_desc and meta_desc.get('content'):
                desc = meta_desc.get('content').strip()

        if desc:
            if len(desc) > 350:
                desc = desc[:347] + "..."
            
            try:
                desc = GoogleTranslator(source='auto', target='pt').translate(desc)
            except Exception as e:
                print(f"Erro ao traduzir a descrição: {e}")
            return desc
    except Exception as e:
        print(f"Erro ao buscar descrição da página do jogo: {e}")
    return None

def send_webhook(title, link, image_url=None, description=None):
    if not WEBHOOK_URL:
        print("Erro: A variável de ambiente DISCORD_WEBHOOK_URL não foi definida.")
        return False

    desc_text = f"**[{title}]({link})**\n\n"
    if description:
        desc_text += f"> {description}\n\n"
    desc_text += "Confira o novo lançamento no Online-Fix."

    embed = {
        "title": "🎮 Novo Jogo Postado!",
        "description": desc_text,
        "color": 7506394,  # Cor roxa/azul escuro
        "footer": {"text": "SkuLL Bot"}
    }

    if image_url:
        embed["image"] = {"url": image_url}

    try:
        response = requests.post(WEBHOOK_URL, json={"embeds": [embed]}, timeout=15)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Erro ao enviar a notificação no Discord: {e}")
        return False

def main():
    print("🚀 Iniciando a nova versão do bot (sem cloudscraper)...")

    last_game_link = ""
    if os.path.exists(LAST_GAME_FILE):
        with open(LAST_GAME_FILE, 'r', encoding='utf-8') as f:
            last_game_link = f.read().strip()

    new_games = get_latest_games(last_game_link)
    
    if not new_games:
        print("Nenhum jogo novo detectado.")
        return
        
    # Se for a primeira vez rodando, pega só o mais recente para não inundar o Discord com 15 jogos de uma vez
    if not last_game_link or TEST_MODE:
        new_games = [new_games[-1]]

    for game in new_games:
        print(f"Novo jogo detectado: {game['title']}")
        print("Buscando descrição na página do jogo...")
        description = get_game_description(game['link'])
        
        if send_webhook(game['title'], game['link'], game['image_url'], description):
            # Atualiza a memória com o link de CADA jogo enviado com sucesso
            with open(LAST_GAME_FILE, 'w', encoding='utf-8') as f:
                f.write(game['link'])

if __name__ == "__main__":
    main()
