"""Gravador local do MEC-Serviços, com a narração Maria já gerada.

Execute na pasta MEC-Servicos. Uma página local abrirá no navegador. Escolha
o perfil, clique em Testar ou Gravar e selecione a aba/janela do programa.
Você navega pelas telas; o gravador une a captura à narração e salva o vídeo.
Não instala pacotes, não acessa o banco e não envia os vídeos à internet.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import shutil
import sys
import threading
import uuid
from urllib.parse import urlsplit
import wave
import webbrowser

REVISION = "MEC-SERVICOS-GRAVADOR-LOCAL-NARRADO-2026-10-14"
PERFIS = ("CLIENTE", "FORNECEDOR", "ADMINISTRADOR")
MAX_VIDEO = 1024 * 1024 * 1024

HTML = r'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MEC-Serviços · Gravação com narração</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#eef3f7;color:#17374b;font:17px/1.5 system-ui,sans-serif}header{padding:25px max(24px,calc((100vw - 1100px)/2));background:#102b3e;color:white}header small{letter-spacing:.09em;color:#bad4e4}h1{font-size:29px;margin:7px 0}header p{margin:8px 0;max-width:980px}main{max-width:1150px;margin:auto;padding:24px}.painel{background:white;border:1px solid #d5e0e9;border-radius:14px;padding:22px;margin-bottom:20px}.linha{display:flex;align-items:center;gap:12px;flex-wrap:wrap}label{font-weight:650}select,button{font:inherit;padding:11px 15px;border-radius:9px;border:1px solid #b6c9d7;background:white;color:#17374b}button{cursor:pointer;font-weight:650}button:disabled{opacity:.5;cursor:default}button:focus-visible,select:focus-visible{outline:3px solid #6abac6;outline-offset:3px}.principal{background:#087f70;color:white;border-color:#087f70}.parar{color:#992a38;border-color:#ce8892}.cinza{color:#577081;font-size:15px}#aviso{padding:14px 17px;background:#e4f3ef;border-radius:9px;margin-top:17px;white-space:pre-line}#aviso.erro{background:#fff0e8;color:#973d17}progress{width:100%;height:13px;accent-color:#087f70;margin-top:18px}.guia{display:grid;grid-template-columns:1.05fr 1fr;gap:20px}video{display:block;width:100%;min-height:180px;max-height:360px;background:#102b3e;border-radius:9px}h2{font-size:22px;margin:0 0 12px}#etapa{color:#087f70;font-weight:700}#fala{font-size:20px;line-height:1.55;min-height:125px}#roteiro{max-height:400px;overflow:auto;margin:0;padding-left:26px}#roteiro li{padding:9px 10px;border-radius:7px}#roteiro .ativo{background:#e4f3ef;font-weight:650}#salvos{overflow-wrap:anywhere}#salvos p{margin:8px 0}.nota{padding:12px;background:#f2f6fa;border-radius:8px}a{color:#2466d1}@media(max-width:800px){.guia{grid-template-columns:1fr}main{padding:14px}h1{font-size:24px}}
</style></head><body>
<header><small>MEC-SERVIÇOS · GRAVADOR LOCAL</small><h1>Telas reais com narração em português</h1><p>Abra o MEC-Serviços em outra aba ou janela. Você faz as operações no programa; este gravador registra a janela escolhida e acrescenta a voz Maria.</p></header>
<main><section class="painel"><div class="linha"><label for="perfil">Perfil</label><select id="perfil"></select><span id="duracao" class="cinza"></span></div>
<p>Comece com <strong>Testar por 10 segundos</strong>. Na escolha do navegador, selecione somente a aba ou janela do MEC-Serviços. Depois de compartilhar, haverá uma contagem de três segundos para você voltar ao programa.</p>
<div class="linha"><button id="teste">Testar por 10 segundos</button><button id="gravar" class="principal">Gravar este perfil</button><button id="pausar" disabled>Pausar</button><button id="parar" class="parar" disabled>Finalizar gravação</button></div>
<div id="aviso" role="status">Preparando a narração…</div><progress id="progresso" value="0" max="1"></progress><div class="linha"><span id="tempo" class="cinza">00:00</span><span class="cinza">Use Pausar se precisar de mais tempo para preparar a próxima tela.</span></div></section>
<div class="guia"><section class="painel"><h2>Narração e roteiro</h2><div id="etapa"></div><p id="fala"></p><ol id="roteiro"></ol></section><section class="painel"><h2>Janela selecionada</h2><video id="previa" muted autoplay playsinline></video><p class="cinza">Esta prévia deve mostrar o programa que você deseja gravar. O microfone e o áudio do computador não são capturados; o vídeo recebe somente a narração preparada.</p><div class="nota">Use um atendimento de demonstração. Os números e valores citados na narração são exemplos. As legendas ficam em um arquivo SRT ao lado do vídeo.</div></section></div>
<section class="painel"><h2>Vídeos salvos no computador</h2><div id="salvos">Nenhuma gravação salva nesta sessão.</div><p class="cinza">O formato será MP4 quando o navegador permitir; caso contrário, será WebM. A pasta completa aparece após salvar e também no PowerShell.</p></section></main>
<script>
const CFG=__CONFIG__;
const $=id=>document.getElementById(id),perfil=$('perfil'),aviso=$('aviso'),previa=$('previa');
let ctx=null,buffers={},dadosAudio={},captura=null,gravador=null,fonte=null,destino=null,chunks=[],comeco=0,offset=0,emGravacao=false,pausado=false,salvando=false,tipoTeste=false,timer=null,timeoutTeste=null,indiceAtual=-1,ultimoBlob=null,ultimoPerfil=null,ultimaDuracao=0;
function informar(t,erro=false){aviso.textContent=t;aviso.className=erro?'erro':'';}
function relogio(t){const s=Math.max(0,Math.floor(t));return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0');}
function p(){return CFG.perfis.find(x=>x.perfil===perfil.value);}
function agora(){return Math.min(p().duracao_segundos,offset+(emGravacao&&!pausado?ctx.currentTime-comeco:0));}
function controles(){const bloqueado=emGravacao||salvando;perfil.disabled=bloqueado;$('gravar').disabled=bloqueado||!dadosAudio[perfil.value];$('teste').disabled=$('gravar').disabled;$('pausar').disabled=!emGravacao;$('parar').disabled=!emGravacao;}
function atualizar(){const t=emGravacao?agora():offset,info=p();$('progresso').max=info.duracao_segundos;$('progresso').value=t;$('tempo').textContent=relogio(t)+' / '+relogio(info.duracao_segundos);let i=info.cenas.findIndex(c=>t>=c.inicio_segundos&&t<c.fim_segundos);if(i<0)i=t>=info.duracao_segundos?info.cenas.length-1:0;if(i!==indiceAtual){indiceAtual=i;const c=info.cenas[i];$('etapa').textContent=`Etapa ${i+1}/${info.cenas.length} · ${c.etapa}`;$('fala').textContent=c.texto_legenda;$('roteiro').querySelectorAll('li').forEach((li,k)=>li.classList.toggle('ativo',k===i));}}
async function escolher(){offset=0;indiceAtual=-1;const info=p();$('duracao').textContent=relogio(info.duracao_segundos)+' de narração';$('roteiro').replaceChildren(...info.cenas.map(c=>{const li=document.createElement('li');li.textContent=relogio(c.inicio_segundos)+' · '+c.titulo;return li;}));atualizar();controles();if(!dadosAudio[info.perfil]){informar('Carregando a narração deste perfil…');try{const r=await fetch('/audio/'+info.perfil);if(!r.ok)throw Error('Não foi possível abrir o áudio.');dadosAudio[info.perfil]=await r.arrayBuffer();}catch(e){informar(e.message,true);controles();return;}}informar('Narração pronta. Abra o programa e faça primeiro o teste de 10 segundos.');controles();}
async function prepararAudio(id){ctx ||= new AudioContext();await ctx.resume();if(!buffers[id])buffers[id]=await ctx.decodeAudioData(dadosAudio[id].slice(0));return buffers[id];}
function tocar(){fonte=ctx.createBufferSource();fonte.buffer=buffers[perfil.value];fonte.connect(ctx.destination);fonte.connect(destino);fonte.onended=()=>{if(emGravacao&&!pausado)finalizar();};comeco=ctx.currentTime;fonte.start(0,offset);}
function pararVoz(){if(fonte){fonte.onended=null;try{fonte.stop();}catch{}fonte.disconnect();fonte=null;}}
function novoGravador(stream){const opcoes=['video/mp4;codecs=avc1.42E01E,mp4a.40.2','video/mp4','video/webm;codecs=vp9,opus','video/webm;codecs=vp8,opus','video/webm'];for(const mimeType of opcoes){if(!MediaRecorder.isTypeSupported(mimeType))continue;try{return new MediaRecorder(stream,{mimeType,videoBitsPerSecond:2400000,audioBitsPerSecond:96000});}catch{}}return new MediaRecorder(stream);}
async function iniciar(teste){
 if(emGravacao||salvando)return;
 if(!navigator.mediaDevices?.getDisplayMedia||!window.MediaRecorder){informar('Abra este endereço no Chrome ou Edge para gravar a janela.',true);return;}
 tipoTeste=teste;salvando=true;controles();informar('Escolha a aba ou janela do MEC-Serviços para a gravação.');
 try{
  ctx ||= new AudioContext();void ctx.resume();
  // A seleção só ocorre após o clique do usuário; não pede microfone nem áudio do sistema.
  captura=await navigator.mediaDevices.getDisplayMedia({video:{frameRate:{ideal:15,max:20},width:{ideal:1920},height:{ideal:1080}},audio:false});
  await prepararAudio(perfil.value);previa.srcObject=captura;await previa.play();
  destino=ctx.createMediaStreamDestination();const combinado=new MediaStream([...captura.getVideoTracks(),...destino.stream.getAudioTracks()]);
  gravador=novoGravador(combinado);chunks=[];offset=0;indiceAtual=-1;
  gravador.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
  gravador.onerror=e=>{informar('O navegador encontrou um erro de gravação: '+(e.error?.message||'erro de mídia'),true);if(emGravacao)finalizar();};
  gravador.onstop=()=>{const blob=new Blob(chunks,{type:gravador.mimeType||'video/webm'});ultimoBlob=blob;ultimoPerfil=perfil.value;salvar(blob,ultimoPerfil,ultimaDuracao,tipoTeste);};
  const track=captura.getVideoTracks()[0];track.addEventListener('ended',()=>{if(emGravacao)finalizar();});
  for(let n=3;n>0;n--){informar('Começa em '+n+'… Volte à aba do programa.');await new Promise(r=>setTimeout(r,1000));if(track.readyState==='ended')throw Error('A captura da janela foi encerrada.');}
  salvando=false;emGravacao=true;pausado=false;gravador.start(2000);tocar();
  timer=setInterval(atualizar,150);if(teste)timeoutTeste=setTimeout(finalizar,10000);
  informar(teste?'Teste em gravação. Navegue ou mova o mouse no programa.':'Gravando. Navegue no programa acompanhando a narração.');controles();
 }catch(e){pararVoz();captura?.getTracks().forEach(t=>t.stop());previa.srcObject=null;salvando=false;emGravacao=false;informar(e.name==='NotAllowedError'?'A janela não foi selecionada ou a captura foi cancelada. Clique em Testar para tentar novamente.':e.message,true);controles();}
}
function pausar(){if(!emGravacao)return;if(!pausado){offset=agora();pausado=true;pararVoz();gravador.pause();$('pausar').textContent='Continuar';informar('Pausado. Prepare a próxima tela e clique em Continuar.');if(timeoutTeste){clearTimeout(timeoutTeste);timeoutTeste=null;}}else{pausado=false;gravador.resume();tocar();$('pausar').textContent='Pausar';informar('Gravação retomada.');if(tipoTeste)timeoutTeste=setTimeout(finalizar,Math.max(0,10-offset)*1000);}controles();}
function finalizar(){if(!emGravacao)return;ultimaDuracao=agora();offset=ultimaDuracao;emGravacao=false;salvando=true;pararVoz();clearInterval(timer);clearTimeout(timeoutTeste);timer=null;timeoutTeste=null;pausado=false;$('pausar').textContent='Pausar';informar('Finalizando e salvando o vídeo no computador…');controles();if(gravador.state!=='inactive')gravador.stop();captura?.getTracks().forEach(t=>t.stop());destino?.stream.getTracks().forEach(t=>t.stop());previa.srcObject=null;atualizar();}
async function salvar(blob,id,segundos,teste){try{if(blob.size<1024)throw Error('O navegador não entregou um vídeo válido.');const r=await fetch('/salvar/'+id,{method:'POST',headers:{'Content-Type':blob.type,'X-MEC-Gravacao':CFG.token,'X-MEC-Segundos':String(segundos),'X-MEC-Teste':teste?'1':'0'},body:blob});const d=await r.json();if(!r.ok)throw Error(d.erro||'Não foi possível salvar o vídeo.');const par=document.createElement('p');par.textContent=(teste?'Teste':d.completo?'Vídeo completo':'Gravação parcial')+' · '+id+': '+d.arquivo;if($('salvos').textContent.startsWith('Nenhuma'))$('salvos').replaceChildren();$('salvos').append(par);informar((teste?'Teste salvo. Abra o arquivo para conferir a janela e a narração.':d.completo?'Vídeo completo salvo. Escolha o próximo perfil para continuar.':'Gravação parcial salva. Você pode regravar o perfil para concluir.')+'\n'+d.caminho);ultimoBlob=null;}catch(e){informar(e.message+' O vídeo também pode ser baixado pelo botão abaixo.',true);const b=document.createElement('button');b.textContent='Baixar vídeo desta tentativa';b.onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='MEC_SERVICOS_VIDEO_REAL_'+id+(blob.type.startsWith('video/mp4')?'.mp4':'.webm');a.click();setTimeout(()=>URL.revokeObjectURL(a.href),30000);};$('salvos').append(b);}finally{salvando=false;controles();}}
for(const info of CFG.perfis){const o=document.createElement('option');o.value=info.perfil;o.textContent=info.nome;perfil.append(o);}
perfil.addEventListener('change',escolher);$('gravar').addEventListener('click',()=>iniciar(false));$('teste').addEventListener('click',()=>iniciar(true));$('pausar').addEventListener('click',pausar);$('parar').addEventListener('click',finalizar);
window.addEventListener('beforeunload',e=>{if(emGravacao||salvando){e.preventDefault();e.returnValue='';}});escolher();
</script></body></html>'''


def localizar_audios(base: Path, informada: str | None = None) -> tuple[Path, list[dict]]:
    candidatos = [Path(informada).expanduser().resolve()] if informada else sorted((base / "_mec_videos/narracoes").glob("*/MEC_NARRACOES_MANIFESTO.json"), reverse=True)
    for candidato in candidatos:
        manifesto = candidato / "MEC_NARRACOES_MANIFESTO.json" if candidato.is_dir() else candidato
        if not manifesto.is_file():
            continue
        dados = json.loads(manifesto.read_text(encoding="utf-8-sig"))
        if {p.get("perfil") for p in dados.get("perfis", [])} != set(PERFIS):
            continue
        perfis = []
        for item in dados["perfis"]:
            perfil = item["perfil"]
            nome = f"MEC_SERVICOS_NARRACAO_{perfil}.wav"
            arquivo = manifesto.parent / nome
            if arquivo.is_symlink() or not arquivo.is_file():
                raise RuntimeError("Áudio não encontrado ou não regular: " + str(arquivo))
            with wave.open(str(arquivo), "rb") as audio:
                duracao = audio.getnframes() / audio.getframerate()
                if audio.getcomptype() != "NONE" or not 0 < duracao <= 3600:
                    raise RuntimeError("Áudio não compatível: " + nome)
            if abs(duracao - float(item["duracao_segundos"])) > .1:
                raise RuntimeError("A duração do áudio não coincide com o roteiro: " + nome)
            anterior = 0.0
            for cena in item["cenas"]:
                inicio, fim = float(cena["inicio_segundos"]), float(cena["fim_segundos"])
                if not math.isfinite(inicio + fim) or abs(inicio - anterior) > .01 or fim <= inicio or fim > duracao + .1:
                    raise RuntimeError("Tempos inválidos no roteiro de " + perfil)
                anterior = fim
            if not item["cenas"] or abs(anterior - duracao) > .1:
                raise RuntimeError("Roteiro incompleto de " + perfil)
            perfis.append({"perfil": perfil, "nome": perfil.title() if perfil != "ADMINISTRADOR" else "Administrador", "duracao_segundos": duracao, "cenas": item["cenas"], "arquivo_audio": str(arquivo.resolve())})
        return manifesto.parent, sorted(perfis, key=lambda p: PERFIS.index(p["perfil"]))
    raise RuntimeError("Narrações não encontradas. Salve este script na pasta MEC-Servicos, onde existe _mec_videos/narracoes. Ou informe --narracoes PASTA_DOS_AUDIOS.")


def timestamp(segundos: float) -> str:
    ms = round(segundos * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def legenda(perfil: dict, fim: float) -> str:
    import textwrap
    linhas = []
    for cena in perfil["cenas"]:
        inicio = float(cena["inicio_segundos"])
        if inicio >= fim:
            break
        ate = min(float(cena["fim_segundos"]), fim)
        linhas.append(f"{len(linhas)+1}\n{timestamp(inicio)} --> {timestamp(ate)}\n" + "\n".join(textwrap.wrap(cena["texto_legenda"], 78)) + "\n")
    return "\n".join(linhas)


def criar_servidor(perfis: list[dict], saida: Path) -> ThreadingHTTPServer:
    token = secrets.token_urlsafe(32)
    mapa = {p["perfil"]: p for p in perfis}
    publico = [{k: v for k, v in p.items() if k != "arquivo_audio"} for p in perfis]
    config = json.dumps({"token": token, "perfis": publico}, ensure_ascii=False).replace("<", "\\u003c")
    pagina = HTML.replace("__CONFIG__", config).encode("utf-8")
    saida.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def permitido(self) -> bool:
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def responder(self, codigo: int, dados: bytes, tipo: str):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(dados)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            self.end_headers()
            self.wfile.write(dados)

        def json(self, codigo, dados):
            self.responder(codigo, json.dumps(dados, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def do_GET(self):
            if not self.permitido():
                return self.json(403, {"erro": "Endereço local não autorizado."})
            caminho = urlsplit(self.path).path
            if caminho == "/":
                return self.responder(200, pagina, "text/html; charset=utf-8")
            if caminho.startswith("/audio/") and caminho[7:] in mapa:
                arquivo = Path(mapa[caminho[7:]]["arquivo_audio"])
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(arquivo.stat().st_size))
                self.send_header("Cache-Control", "private, max-age=3600")
                self.end_headers()
                with arquivo.open("rb") as fonte:
                    shutil.copyfileobj(fonte, self.wfile, 1024*1024)
                return
            self.json(404, {"erro": "Recurso não encontrado."})

        def do_POST(self):
            origem = f"http://127.0.0.1:{self.server.server_port}"
            recebido = self.headers.get("X-MEC-Gravacao", "")
            if not self.permitido() or self.headers.get("Origin") not in (None, origem) or not secrets.compare_digest(recebido, token):
                return self.json(403, {"erro": "Gravação não autorizada por esta página local."})
            caminho = urlsplit(self.path).path
            perfil = mapa.get(caminho.removeprefix("/salvar/")) if caminho.startswith("/salvar/") else None
            if perfil is None:
                return self.json(404, {"erro": "Perfil inválido."})
            tipo = self.headers.get("Content-Type", "").split(";", 1)[0].strip()
            if tipo not in ("video/mp4", "video/webm"):
                return self.json(400, {"erro": "Formato de vídeo não aceito."})
            try:
                tamanho = int(self.headers.get("Content-Length", "0"))
                segundos = float(self.headers.get("X-MEC-Segundos", "0"))
                if not 1024 <= tamanho <= MAX_VIDEO or not math.isfinite(segundos) or not 0 < segundos <= perfil["duracao_segundos"] + 2:
                    raise ValueError
            except ValueError:
                return self.json(400, {"erro": "Tamanho ou duração inválidos."})
            teste = self.headers.get("X-MEC-Teste") == "1"
            marca = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
            nome = ("MEC_SERVICOS_TESTE_" if teste else "MEC_SERVICOS_VIDEO_REAL_") + perfil["perfil"] + "_" + marca + (".mp4" if tipo == "video/mp4" else ".webm")
            final = saida / nome
            parcial = final.with_suffix(final.suffix + ".part")
            try:
                self.connection.settimeout(180)
                restante = tamanho
                primeiro = True
                with parcial.open("xb") as destino:
                    while restante:
                        bloco = self.rfile.read(min(restante, 1024*1024))
                        if not bloco:
                            raise RuntimeError("O envio do vídeo foi interrompido.")
                        if primeiro:
                            valido = (bloco[4:8] == b"ftyp") if tipo == "video/mp4" else bloco[:4] == b"\x1a\x45\xdf\xa3"
                            if not valido:
                                raise RuntimeError("O conteúdo recebido não corresponde ao formato informado.")
                            primeiro = False
                        destino.write(bloco)
                        restante -= len(bloco)
                parcial.replace(final)
                final.with_suffix(".srt").write_text(legenda(perfil, segundos), encoding="utf-8")
                completo = not teste and segundos >= perfil["duracao_segundos"] - .3
                dados = {"revision": REVISION, "perfil": perfil["perfil"], "voz": "Microsoft Maria Desktop", "arquivo": nome, "bytes": tamanho, "duracao_informada_segundos": segundos, "teste": teste, "completo": completo, "formato": tipo}
                final.with_suffix(".json").write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
                print("VIDEO_SALVO=" + str(final), flush=True)
                self.json(200, {"arquivo": nome, "caminho": str(final), "completo": completo})
            except Exception as erro:
                self.json(400, {"erro": str(erro)})
            finally:
                parcial.unlink(missing_ok=True)

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--narracoes", help="Pasta ou manifesto das narrações já geradas.")
    parser.add_argument("--sem-abrir", action="store_true", help="Exibe o endereço sem abrir o navegador automaticamente.")
    args = parser.parse_args(argv)
    print("MEC-Serviços — Gravador local com narração", flush=True)
    print("REVISION=" + REVISION, flush=True)
    servidor = None
    try:
        base = Path(__file__).resolve().parent
        pasta_audio, perfis = localizar_audios(base, args.narracoes)
        marca = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
        saida = base / "_mec_videos" / "videos_reais" / marca
        servidor = criar_servidor(perfis, saida)
        endereco = f"http://127.0.0.1:{servidor.server_port}/"
        print("NARRACOES=" + str(pasta_audio), flush=True)
        print("PASTA_SAIDA=" + str(saida), flush=True)
        print("ENDERECO=" + endereco, flush=True)
        print("GRAVADOR_PRONTO=True", flush=True)
        print("Mantenha este PowerShell aberto. Use Chrome ou Edge e comece pelo teste de 10 segundos.", flush=True)
        print("Você navega no MEC-Serviços durante a narração. Este gravador não preenche os formulários automaticamente.", flush=True)
        print("Pressione Ctrl+C aqui depois de concluir os três perfis.", flush=True)
        if not args.sem_abrir:
            threading.Timer(.5, lambda: webbrowser.open(endereco)).start()
        servidor.serve_forever(poll_interval=.3)
    except KeyboardInterrupt:
        print("GRAVADOR_ENCERRADO=True", flush=True)
        return 0
    except Exception as erro:
        print("ERRO=" + str(erro), flush=True)
        return 1
    finally:
        if servidor is not None:
            servidor.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
