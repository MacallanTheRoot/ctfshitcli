import asyncio
import logging
import json
from pathlib import Path
import aiohttp
from rich.markdown import Markdown
from rich.console import Console
from rich.status import Status

logger = logging.getLogger(__name__)
console = Console()

async def analyze_challenge_with_llm(challenge_dir: Path, api_key: str) -> bool:
    """
    Reads source code files in the challenge directory and sends them to Gemini for analysis.
    
    Args:
        challenge_dir: Path to the challenge directory.
        api_key: Gemini API key.
        
    Returns:
        True if successful, False otherwise.
    """
    if not api_key:
        logger.error("LLM API key is missing.")
        return False
        
    console.print(f"[*] Analyzing challenge directory: {challenge_dir}")
    
    # 1. Gather context
    extensions_to_read = {".c", ".py", ".php", ".txt", ".js", ".go", ".rs", ".md", ".json"}
    context_parts = []
    
    for file_path in challenge_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix in extensions_to_read:
            try:
                # Read file content safely
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Limit size per file to prevent overwhelming the context (e.g. 50KB)
                if len(content) > 50000:
                    content = content[:50000] + "\n...[TRUNCATED]"
                    
                context_parts.append(f"--- File: {file_path.relative_to(challenge_dir)} ---\n{content}\n")
            except Exception as e:
                logger.warning(f"Could not read file {file_path}: {e}")
                
    if not context_parts:
        console.print("[red][-] No readable source code files found in the directory.[/red]")
        return False
        
    full_context = "\n".join(context_parts)
    
    # 2. Prepare API Request
    models_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    
    system_prompt = (
        "Sen Cyberpunk estetiğine sahip, yetenekli bir Red Team ve CTF uzmanısın. "
        "Aşağıdaki kaynak kodları ve soru açıklamasını inceleyerek zafiyeti bul, "
        "bana exploit stratejisini veya kodu nasıl refactor etmem gerektiğini "
        "karanlık ve profesyonel bir tonda anlat."
    )
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": system_prompt + "\n\n" + full_context}
                ]
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # 3. Send request and display response
    with Status("[cyan]Görsel korteks bağlanıyor... Uygun model taranıyor...[/cyan]", console=console):
        try:
            async with aiohttp.ClientSession() as session:
                # --- Step 1: Auto-discover the best model ---
                async with session.get(models_url, timeout=15) as models_response:
                    if models_response.status != 200:
                        err = await models_response.text()
                        logger.error(f"Models API Error {models_response.status}: {err}")
                        console.print(f"[red][-] API Anahtarı Doğrulanamadı: HTTP {models_response.status}[/red]")
                        console.print(f"[red]Detay: {err}[/red]")
                        return False
                        
                    models_data = await models_response.json()
                    supported_models = [
                        m["name"] for m in models_data.get("models", [])
                        if "generateContent" in m.get("supportedGenerationMethods", [])
                    ]
                    
                    if not supported_models:
                        console.print("[red][-] Bu API anahtarı için 'generateContent' destekleyen hiçbir model bulunamadı.[/red]")
                        return False
                        
                    # Order models based on preference
                    ordered_models = []
                    preferences = [
                        "models/gemini-2.5-pro", 
                        "models/gemini-2.5-flash", 
                        "models/gemini-1.5-pro", 
                        "models/gemini-1.5-flash", 
                        "models/gemini-pro"
                    ]
                    
                    for pref in preferences:
                        if pref in supported_models:
                            ordered_models.append(pref)
                            
                    for m in supported_models:
                        if m not in ordered_models:
                            ordered_models.append(m)
                            
                if not ordered_models:
                    console.print("[red][-] Bu API anahtarı için geçerli bir model bulunamadı.[/red]")
                    return False
                
                # --- Step 2: Generate Content (with fallback) ---
                for best_model in ordered_models:
                    console.print(f"[*] Hedef kilitlendi: [bold green]{best_model}[/bold green]")
                    generate_url = f"https://generativelanguage.googleapis.com/v1beta/{best_model}:generateContent?key={api_key}"
                    
                    async with session.post(generate_url, headers=headers, json=payload, timeout=60) as response:
                        if response.status == 200:
                            data = await response.json()
                            try:
                                reply_text = data["candidates"][0]["content"]["parts"][0]["text"]
                                console.print("\n[bold cyan]=== OTONOM SİBER SİSTEM ANALİZ RAPORU ===[/bold cyan]\n")
                                console.print(Markdown(reply_text))
                                console.print("\n[bold cyan]==============================================[/bold cyan]\n")
                                return True
                            except (KeyError, IndexError) as e:
                                logger.error(f"Unexpected API response format: {e}")
                                console.print("[red][-] Beklenmeyen veri akışı... Parse hatası.[/red]")
                                return False
                                
                        elif response.status in (503, 429):
                            # Server overloaded or quota exceeded, try the next model
                            console.print(f"[yellow][!] {best_model} kullanılamıyor (HTTP {response.status}). Alternatif modele geçiliyor...[/yellow]")
                            continue
                            
                        else:
                            error_text = await response.text()
                            logger.error(f"LLM API Error {response.status}: {error_text}")
                            console.print(f"[red][-] Neural network arızası: HTTP {response.status}[/red]")
                            console.print(f"[red]Detay: {error_text}[/red]")
                            return False
                            
                console.print("[red][-] Bütün uygun modeller denendi ancak Google sunucuları şu an çok yoğun (503). Lütfen daha sonra tekrar dene.[/red]")
                return False
                        
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            console.print(f"[red][-] Sisteme bağlanılamadı: {e}[/red]")
            return False
