# main.py
from pplay.window import Window
from pplay.gameimage import GameImage
from pplay.sprite import Sprite
import config
from entidades import Echo, Eco, Portal, Plataforma, Sentinela, Laser, Coletavel
import pygame
import json
import datetime

# Estado extra (não existe no config.py): digitação do nome
ESTADO_NOME = 5

ARQUIVO_RANKING = "ranking.json"


# ==========================================================
# RANKING (persistido em ranking.json)
# ==========================================================
def formatar_tempo(segundos):
    """mm:ss.d — ex.: 02:37.4"""
    m = int(segundos // 60)
    s = int(segundos % 60)
    d = int((segundos * 10) % 10)
    return f"{m:02d}:{s:02d}.{d}"


def carregar_ranking():
    """Lê o ranking do disco, sempre ordenado do menor tempo
    para o maior."""
    try:
        with open(ARQUIVO_RANKING, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return sorted(dados, key=lambda r: r.get("tempo", 999999))
    except Exception:
        return []


def salvar_no_ranking(nome, tempo):
    """Acrescenta uma entrada {nome, tempo, data} e regrava o
    arquivo ordenado. Retorna o ranking atualizado."""
    ranking = carregar_ranking()
    ranking.append({
        "nome": nome,
        "tempo": round(tempo, 1),
        "data": datetime.date.today().strftime("%d/%m/%Y"),
    })
    ranking.sort(key=lambda r: r.get("tempo", 999999))
    try:
        with open(ARQUIVO_RANKING, "w", encoding="utf-8") as f:
            json.dump(ranking, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Erro ao salvar ranking:", e)
    return ranking


# ==========================================================
# FÁBRICA DE FASES (PUZZLES)
# ==========================================================
def pedestal_para(sentinela):
    """Cria uma plataforma de apoio exatamente sob uma sentinela
    flutuante: a laje visível encosta na base visível da torre."""
    p = Plataforma(0, 0)
    rv = p.rect_visual
    base_torre = sentinela.y + sentinela.rect_visual.bottom
    centro_torre = sentinela.x + sentinela.rect_visual.centerx
    p.set_position(centro_torre - rv.centerx, base_torre - rv.top)
    return p


def criar_fase(numero):
    """
    Cria e retorna todas as entidades de uma fase.
    Todo o level design fica centralizado aqui.

    NOTAS DE FÍSICA (usadas para calibrar os vãos):
    - O pouso acontece no TOPO VISÍVEL da laje (plat.y + 46);
      de pé numa plataforma, echo.y = plat.y - 59.
    - Altura máx. do pulo: 120px. Do chão só se alcançam lajes
      com plat.y >= ~520; de uma plataforma, ~130px acima.
    - Subir na cabeça de um clone dá ~100px extras. VÃOS
      MAIORES QUE O PULO SÓ SE VENCEM EMPILHANDO CLONES.
    - Torre visível da sentinela: x+73..x+170 (flip ESQUERDA).
      Para aparecer inteira: -73 <= x <= 1105.
    - As rasantes têm ALCANCE limitado: o começo do mapa é uma
      zona segura para gravar clones com calma.
    - REGRA DO PORTAL: só funciona com os 3 cubos da fase.
    """
    fase = {"portal": None, "plataformas": [], "sentinelas": [], "coletaveis": []}

    if numero == 1:
       
        fase["portal"] = Portal(1145, 193)   # sobre o degrau C

        fase["plataformas"] = [
            Plataforma(800, 575),    # degrau A (alcançável do chão)
            Plataforma(950, 380),    # degrau B (SÓ com clone-escada em A)
            Plataforma(1090, 280),   # degrau C — plataforma do portal
        ]

        # S1 — rasante do corredor. Alcance 460: os lasers morrem
        # em x~225, deixando o spawn/zona de gravação em paz.
        s1 = Sentinela(620, 0, "ESQUERDA", cooldown=0.95, vel_laser=480,
                       timer_inicial=0.0, alcance=460)
        s1.apoiar_no_chao()

        # S2 — anti-pulo / anti-escada (visível: x 1178..1275)
        s2 = Sentinela(1105, 0, "ESQUERDA", cooldown=2.2, vel_laser=420, timer_inicial=1.1)
        s2.posicionar_cano_em(505)

        # S3 — guarda o degrau B e os saltos dos cubos 1 e 3
        s3 = Sentinela(-70, 0, "DIREITA", cooldown=2.4, vel_laser=400, timer_inicial=0.0)
        s3.posicionar_cano_em(410)

        fase["sentinelas"] = [s1, s2, s3]

        # Pedestais sob as torres flutuantes (S1 já está no chão)
        fase["plataformas"] += [pedestal_para(s2), pedestal_para(s3)]

        fase["coletaveis"] = [
            Coletavel(80, 340),      # 1: MIRANTE (esquerda do mapa)
            Coletavel(1090, 450),    # 2: BOCA DO CANHÃO da S2 (direita)
            Coletavel(1040, 250),    # 3: arco do salto B→C (topo)
        ]

    elif numero == 2:
        # ==================================================
        # FASE 2 — "ESCALADA SINCRONIZADA"
        #
        # A TORRE: P2 (545) alcançável do chão; P3 (345) e
        # P4 (150) ficam a DOIS vãos impossíveis — empilhar é
        # obrigatório: clone em P2 → cabeça → P3; clone em
        # P3 → cabeça → P4 → portal.
        #
        # CORREDORES CRUZADOS: SA rasante (alcance limitado —
        # o spawn é seguro) fecha o chão da direita; SB (y~470)
        # varre a cabeça do clone de P2; SC (y~250) varre a
        # cabeça do clone de P3; SD (y~350) varre quem está de
        # pé em P3 — mas o clone empilhado ali ABSORVE esses
        # tiros: seu degrau vira seu escudo.
        #
        # OS 3 CUBOS — espalhados pelos 3 cantos do mapa:
        #  1. BOCA DO CANHÃO DA SD (esquerda): flutua colado no
        #     cano. Puzzle próprio: clone parado na zona segura
        #     do spawn, subir na cabeça e saltar até o cubo à
        #     queima-roupa da SD — com o corredor da SB
        #     cruzando a altura da cabeça do clone.
        #  2. ZONA DE FOGO DA SA (direita, chão): cd 1.0s —
        #     entrar e sair exige clone-escudo na frente.
        #  3. ARCO FINAL (topo): na linha da SC, pego DURANTE
        #     o salto P3→P4 — a jogada mais difícil da fase.
        # ==================================================
        fase["portal"] = Portal(1135, 63)    # sobre P4, lá no topo

        fase["plataformas"] = [
            Plataforma(620, 545),    # P2 (alcançável do chão)
            Plataforma(820, 345),    # P3 (SÓ com clone-escada em P2)
            Plataforma(1080, 150),   # P4 — plataforma do portal
        ]

        # SA — rasante do chão. Alcance 720: lasers morrem em
        # x~450; spawn e zona de gravação à esquerda são seguros.
        sa = Sentinela(1105, 0, "ESQUERDA", cooldown=1.0, vel_laser=480,
                       timer_inicial=0.0, alcance=720)
        sa.apoiar_no_chao()
        # Empurra a torre para o canto inferior direito para
        # TAMPAR a marca d'água do fundo. (Ajuste fino: mexa
        # nesses +7 / +25 se a marca ainda aparecer.)
        sa.set_position(sa.x + 7, sa.y + 25)

        # SB — varre a cabeça do clone de P2 e o pulo no chão
        sb = Sentinela(1105, 0, "ESQUERDA", cooldown=2.0, vel_laser=420, timer_inicial=0.7)
        sb.posicionar_cano_em(470)

        # SC — varre a cabeça do clone de P3 (salto final)
        sc = Sentinela(-70, 0, "DIREITA", cooldown=2.4, vel_laser=400, timer_inicial=0.0)
        sc.posicionar_cano_em(250)

        # SD — varre quem está de pé em P3
        sd = Sentinela(-70, 0, "DIREITA", cooldown=2.6, vel_laser=380, timer_inicial=1.3)
        sd.posicionar_cano_em(350)

        fase["sentinelas"] = [sa, sb, sc, sd]

        # Pedestais sob as torres flutuantes (SA já está no chão)
        fase["plataformas"] += [pedestal_para(sb), pedestal_para(sc), pedestal_para(sd)]

        cubo_chao = Coletavel(1030, 0)
        cubo_chao.apoiar_no_chao()
        fase["coletaveis"] = [
            Coletavel(70, 350),      # 1: BOCA DO CANHÃO da SD (esquerda)
            cubo_chao,               # 2: zona de fogo da SA (direita)
            Coletavel(990, 230),     # 3: arco do salto final (topo)
        ]

    elif numero == 3:
        # ==================================================
        # FASE 3 — "PROTOCOLO FINAL"
        #
        # A ESCADA TRIPLA (esquerda): L1 (545) alcançável do
        # chão; L2 (350) exige clone em L1; TOPO (180) exige
        # OUTRO clone em L2 — dois empilhamentos seguidos.
        # Depois, a TRAVESSIA aérea: TOPO → MID (830, 260) →
        # PF (990, 380), onde está o portal.
        #
        # CORREDORES: SG rasante (atira p/ a DIREITA, alcance
        # limitado) fecha o chão da direita — o lado esquerdo
        # e o spawn são seguros; SH (y~250) varre a cabeça do
        # clone de L2 E a plataforma MID; SI (y~140) varre o
        # TOPO: sem acampar lá em cima; SJ (y~420) varre a
        # cabeça do clone de L1 E a plataforma do portal — a
        # chegada é cronometrada.
        #
        # OS 3 CUBOS — espalhados pelos 3 cantos do mapa:
        #  1. PICO (topo-esquerda): flutua acima do TOPO, na
        #     linha da SI — só após a escada tripla, com um
        #     pulo cronometrado no ponto mais alto do jogo.
        #  2. ZONA DE FOGO (direita, chão): na varredura da SG
        #     — clone-escudo correndo para a DIREITA.
        #  3. TRAVESSIA (centro-alto): flutua no abismo entre
        #     TOPO e MID, cruzado pela linha da SH — pega-se
        #     em pleno voo; errou, caiu no chão varrido.
        # ==================================================
        fase["portal"] = Portal(1045, 293)   # sobre PF

        fase["plataformas"] = [
            Plataforma(150, 545),    # L1 (alcançável do chão)
            Plataforma(330, 350),    # L2 (clone-escada em L1)
            Plataforma(620, 180),    # TOPO (clone-escada em L2)
            Plataforma(830, 260),    # MID — travessia
            Plataforma(990, 380),    # PF — plataforma do portal
        ]

        # SG — rasante atirando para a DIREITA. Alcance 500:
        # cobre x~737..1237; o lado esquerdo do mapa é seguro.
        sg = Sentinela(560, 0, "DIREITA", cooldown=1.0, vel_laser=480,
                       timer_inicial=0.0, alcance=500)
        sg.apoiar_no_chao()

        # SH — varre a cabeça do clone de L2, a MID e o cubo 3
        sh = Sentinela(1105, 0, "ESQUERDA", cooldown=2.2, vel_laser=420, timer_inicial=0.0)
        sh.posicionar_cano_em(250)

        # SI — varre o TOPO e o salto do cubo do Pico
        si = Sentinela(-70, 0, "DIREITA", cooldown=2.6, vel_laser=400, timer_inicial=1.0)
        si.posicionar_cano_em(140)

        # SJ — varre a cabeça do clone de L1 e a chegada ao portal
        sj = Sentinela(1105, 0, "ESQUERDA", cooldown=2.4, vel_laser=410, timer_inicial=1.2)
        sj.posicionar_cano_em(420)

        fase["sentinelas"] = [sg, sh, si, sj]

        # Pedestais sob as torres flutuantes (SG já está no chão)
        fase["plataformas"] += [pedestal_para(sh), pedestal_para(si), pedestal_para(sj)]

        cubo_chao = Coletavel(900, 0)
        cubo_chao.apoiar_no_chao()
        fase["coletaveis"] = [
            Coletavel(660, 60),      # 1: PICO (acima do TOPO, linha da SI)
            cubo_chao,               # 2: zona de fogo da SG (direita)
            Coletavel(760, 190),     # 3: abismo da TRAVESSIA (linha da SH)
        ]

    return fase


# ==========================================================
# JOGO
# ==========================================================
def main():
    janela = Window(config.LARGURA_TELA, config.ALTURA_TELA)
    janela.set_title(config.TITULO)
    teclado = janela.get_keyboard()
    mouse = janela.get_mouse()
    relogio = pygame.time.Clock()

    # === FUNDOS DAS FASES ===
    try:
        fundo_fase1 = GameImage("assets/fase1.jpg")
        fundo_fase1.image = pygame.transform.smoothscale(fundo_fase1.image, (janela.width, janela.height))
    except:
        fundo_fase1 = None

    try:
        fundo_fase2 = GameImage("assets/fase2.jpg")
        fundo_fase2.image = pygame.transform.smoothscale(fundo_fase2.image, (janela.width, janela.height))
    except:
        fundo_fase2 = None

    try:
        fundo_fase3 = GameImage("assets/fase3.jpg")
        fundo_fase3.image = pygame.transform.smoothscale(fundo_fase3.image, (janela.width, janela.height))
    except:
        fundo_fase3 = None

    # Fundo da tela de finalização (para não repetir o menu)
    try:
        fundo_final = GameImage("assets/telafinal.jpg")
        fundo_final.image = pygame.transform.smoothscale(fundo_final.image, (janela.width, janela.height))
    except:
        fundo_final = None

    # Arte do "JOGO COMPLETADO" (substitui o texto verde)
    try:
        img_frase_final = Sprite("assets/frasefinal.png")
        img_frase_final.set_position(janela.width / 2 - img_frase_final.width / 2, 60)
    except:
        img_frase_final = None

    # === FUNDO ANIMADO DO MENU ===
    frames_menu = []
    TOTAL_DE_FRAMES = 151  # frame_000000.jpg ... frame_000150.jpg
    try:
        print("Carregando vídeo do menu em resolução nativa... Aguarde.")
        for i in range(TOTAL_DE_FRAMES):
            frame = GameImage(f"assets/menu_frames/frame_{i:06d}.jpg")
            frames_menu.append(frame)
        print("Vídeo carregado com sucesso!")
    except Exception as e:
        print(f"Aviso: Não achou os frames do vídeo. Erro: {e}")
        frames_menu = []

    frame_atual = 0
    tempo_frame = 0

    # === TÍTULO E BOTÕES ===
    img_titulo = Sprite("assets/titulo.png")
    img_titulo.set_position(janela.width / 2 - img_titulo.width / 2, -40)

    btn_jogar = Sprite("assets/jogar.png")
    btn_jogar.set_position(janela.width / 2 - btn_jogar.width / 2, 200)
    btn_ranking = Sprite("assets/ranking.png")
    btn_ranking.set_position(janela.width / 2 - btn_ranking.width / 2, 280)
    btn_sair = Sprite("assets/sair.png")
    btn_sair.set_position(janela.width / 2 - btn_sair.width / 2, 360)

    btn_facil = Sprite("assets/facil.png")
    btn_facil.set_position(janela.width / 2 - btn_facil.width / 2, 150)
    btn_medio = Sprite("assets/medio.png")
    btn_medio.set_position(janela.width / 2 - btn_medio.width / 2, 250)
    btn_dificil = Sprite("assets/dificil.png")
    btn_dificil.set_position(janela.width / 2 - btn_dificil.width / 2, 350)

    btn_voltar = Sprite("assets/voltar.png")
    btn_voltar.set_position(20, janela.height - btn_voltar.height - 20)

    # === VARIÁVEIS DE CONTROLE ===
    estado_atual = config.MENU
    fase_atual = 1
    fundo_ativo = fundo_fase1
    click_cooldown = 0

    limite_clones = 6    # Definido pela dificuldade

    echo = Echo("echo_andando.png", 100, 100, frames=3)
    ecos = []
    lasers = []
    tecla_e = False
    tecla_q = False

    # --- Temporizador e ranking ---
    tempo_jogo = 0.0        # cronômetro total da run (não zera na morte)
    tempo_final = 0.0       # tempo congelado ao terminar o jogo
    nome_jogador = ""       # digitado na tela de nome
    ranking = carregar_ranking()

    fase = criar_fase(1)

    pygame.mixer.init()
    musica_tocando = None

    # ------------------------------------------------------
    # Funções auxiliares (usam as variáveis locais acima)
    # ------------------------------------------------------
    def resetar_fase():
        """Reseta a fase atual inteira: posição do Echo, clones,
        lasers, cubos coletados e timers das sentinelas.
        (O cronômetro da run NÃO reseta: morrer custa tempo.)"""
        echo.set_position(100, janela.height - config.CHAO_Y_OFFSET - echo.height)
        echo.vel_y = 0
        echo.gravando = False
        echo.historico_acoes.clear()
        ecos.clear()
        lasers.clear()
        for col in fase["coletaveis"]:
            col.coletado = False
        for sent in fase["sentinelas"]:
            sent.timer_tiro = sent.timer_inicial

    def carregar_fase(numero):
        nonlocal fase, fase_atual, fundo_ativo
        fase_atual = numero
        fase = criar_fase(numero)
        fundo_ativo = {1: fundo_fase1, 2: fundo_fase2, 3: fundo_fase3}.get(numero)
        resetar_fase()

    # ======================================================
    # LOOP PRINCIPAL
    # ======================================================
    while True:
        delta_time = janela.delta_time()
        if delta_time > 0.05:
            delta_time = 0.05
        relogio.tick(60)

        if click_cooldown > 0:
            click_cooldown -= delta_time

        # === FUNDO ===
        if estado_atual == config.JOGANDO:
            if fundo_ativo:
                fundo_ativo.draw()
            else:
                janela.set_background_color((10, 15, 20))
        elif estado_atual in (ESTADO_NOME, config.VITORIA) and fundo_final:
            fundo_final.draw()
        else:
            if len(frames_menu) > 0:
                tempo_frame += delta_time
                if tempo_frame > 0.033:
                    frame_atual += 1
                    tempo_frame = 0
                    if frame_atual >= len(frames_menu):
                        frame_atual = 0
                frames_menu[frame_atual].draw()
            else:
                janela.set_background_color((20, 20, 30))

        # === MÚSICA ===
        if estado_atual in [config.MENU, config.DIFICULDADE, config.RANKING]:
            # Só carrega e dá play se a música do menu já não estiver tocando
            if musica_tocando != "MENU":
                try:
                    pygame.mixer.music.load("assets/som_menu.ogg")  # Substitua pelo nome do seu arquivo
                    pygame.mixer.music.set_volume(0.1)  # Volume opcional (0.0 a 1.0)
                    pygame.mixer.music.play(-1)  # O -1 faz a música repetir em loop infinito
                    musica_tocando = "MENU"
                except Exception as e:
                    print("Não achou o som do menu:", e)
                    musica_tocando = "ERRO"

        elif estado_atual == config.JOGANDO:
            if musica_tocando != "FASE":
                try:
                    pygame.mixer.music.load("assets/som_fase.ogg")  # Substitua pelo nome do seu arquivo
                    pygame.mixer.music.set_volume(0.1)  # Deixei o som da fase um pouco mais baixo
                    pygame.mixer.music.play(-1)
                    musica_tocando = "FASE"
                except Exception as e:
                    print("Não achou o som da fase:", e)
                    musica_tocando = "ERRO"

        elif estado_atual in (config.VITORIA, ESTADO_NOME):
            if musica_tocando != "VITORIA":
                pygame.mixer.music.stop()  # Para a música na finalização
                musica_tocando = "VITORIA"

        # ==================================================
        # ESTADO: MENU PRINCIPAL
        # ==================================================
        if estado_atual == config.MENU:
            img_titulo.draw()
            btn_jogar.draw()
            btn_ranking.draw()
            btn_sair.draw()

            # Painel de créditos no canto inferior direito —
            # também serve para TAMPAR a marca d'água do fundo.
            tela = pygame.display.get_surface()
            pygame.draw.rect(tela, (8, 16, 22), (janela.width - 235, janela.height - 190, 235, 105))
            pygame.draw.rect(tela, (0, 180, 200), (janela.width - 235, janela.height - 190, 235, 105), 2)
            janela.draw_text("Feito por:", janela.width - 215, janela.height - 175, size=20, color=(0, 255, 255), bold=True)
            janela.draw_text("Kauê Lopes", janela.width - 215, janela.height - 153, size=20, color=(220, 220, 220))
            janela.draw_text("Arthur Ribeiro", janela.width - 215, janela.height - 127, size=20, color=(220, 220, 220))

            if mouse.is_button_pressed(1) and click_cooldown <= 0:
                if mouse.is_over_object(btn_jogar):
                    estado_atual = config.DIFICULDADE
                    click_cooldown = 0.3
                elif mouse.is_over_object(btn_ranking):
                    ranking = carregar_ranking()
                    estado_atual = config.RANKING
                    click_cooldown = 0.3
                elif mouse.is_over_object(btn_sair):
                    break

        # ==================================================
        # ESTADO: ESCOLHA DE DIFICULDADE
        # ==================================================
        elif estado_atual == config.DIFICULDADE:
            btn_facil.draw()
            btn_medio.draw()
            btn_dificil.draw()
            btn_voltar.draw()

            if mouse.is_button_pressed(1) and click_cooldown <= 0:
                entrar_no_jogo = False

                if mouse.is_over_object(btn_facil):
                    limite_clones = 6
                    entrar_no_jogo = True
                elif mouse.is_over_object(btn_medio):
                    limite_clones = 5
                    entrar_no_jogo = True
                elif mouse.is_over_object(btn_dificil):
                    limite_clones = 4
                    entrar_no_jogo = True
                elif mouse.is_over_object(btn_voltar):
                    estado_atual = config.MENU
                    click_cooldown = 0.3

                if entrar_no_jogo:
                    estado_atual = config.JOGANDO
                    click_cooldown = 0.3
                    tempo_jogo = 0.0   # nova run: cronômetro zera aqui
                    carregar_fase(1)

        # ==================================================
        # ESTADO: RANKING
        # ==================================================
        elif estado_atual == config.RANKING:
            janela.draw_text("RANKING DOS JOGADORES", janela.width / 2 - 190, 70, size=32, color=(255, 255, 255), bold=True)

            # Cabeçalho das colunas
            col_pos = janela.width / 2 - 280
            col_nome = janela.width / 2 - 220
            col_tempo = janela.width / 2 + 60
            col_data = janela.width / 2 + 180
            janela.draw_text("#", col_pos, 130, size=22, color=(0, 255, 255), bold=True)
            janela.draw_text("JOGADOR", col_nome, 130, size=22, color=(0, 255, 255), bold=True)
            janela.draw_text("TEMPO", col_tempo, 130, size=22, color=(0, 255, 255), bold=True)
            janela.draw_text("DATA", col_data, 130, size=22, color=(0, 255, 255), bold=True)

            if len(ranking) == 0:
                janela.draw_text("Nenhum tempo registrado ainda.", janela.width / 2 - 160, 180, size=24, color=(200, 200, 200))
            else:
                for i, entrada in enumerate(ranking[:10]):
                    y = 170 + i * 38
                    cor = (255, 215, 0) if i == 0 else (220, 220, 220)
                    janela.draw_text(f"{i + 1}", col_pos, y, size=22, color=cor)
                    janela.draw_text(str(entrada.get("nome", "?"))[:12], col_nome, y, size=22, color=cor)
                    janela.draw_text(formatar_tempo(entrada.get("tempo", 0)), col_tempo, y, size=22, color=cor)
                    janela.draw_text(str(entrada.get("data", "--/--/----")), col_data, y, size=22, color=cor)

            btn_voltar.draw()

            if mouse.is_button_pressed(1) and click_cooldown <= 0:
                if mouse.is_over_object(btn_voltar):
                    estado_atual = config.MENU
                    click_cooldown = 0.3

        # ==================================================
        # ESTADO: JOGANDO
        # ==================================================
        elif estado_atual == config.JOGANDO:
            tempo_jogo += delta_time
            chao_y = janela.height - config.CHAO_Y_OFFSET - echo.height

            # --- Reset manual (R) ---
            if teclado.key_pressed("R"):
                resetar_fase()

            # --- Gravação (E) ---
            if teclado.key_pressed("E"):
                if not tecla_e:
                    if echo.gravando:
                        echo.gravando = False
                    else:
                        echo.historico_acoes.clear()
                        echo.gravando = True
                    tecla_e = True
            else:
                tecla_e = False

            # --- Spawn de clone (Q) ---
            if teclado.key_pressed("Q"):
                if not tecla_q:
                    if not echo.gravando and len(echo.historico_acoes) > 0 and len(ecos) < limite_clones:
                        novo_eco = Eco("echo_andando.png", echo.historico_acoes, frames=3)
                        ecos.append(novo_eco)
                    tecla_q = True
            else:
                tecla_q = False

            # --- Física do Echo ---
            echo.aplicar_gravidade(delta_time)
            echo.no_chao = False
            if echo.y >= chao_y:
                echo.y = chao_y
                echo.vel_y = 0
                echo.no_chao = True

            # --- Colisão com plataformas (pouso pela LAJE VISÍVEL) ---
            # Os pés visuais precisam CRUZAR o topo visível da laje
            # neste frame (vel_y * delta_time) — sem teletransporte.
            PES_VISUAL = 105  # base do corpo dentro do frame de 112px
            if echo.vel_y > 0:
                pes = echo.y + PES_VISUAL
                pes_antes = pes - echo.vel_y * delta_time
                for plat in fase["plataformas"]:
                    rv = plat.rect_visual
                    topo_laje = plat.y + rv.top
                    borda_esq = plat.x + rv.left + 10
                    borda_dir = plat.x + rv.right - 10
                    sobre_a_laje = (echo.x + echo.width - 15) > borda_esq and (echo.x + 15) < borda_dir
                    if sobre_a_laje and pes_antes <= topo_laje + 6 and pes >= topo_laje:
                        echo.y = topo_laje - PES_VISUAL
                        echo.vel_y = 0
                        echo.no_chao = True
                        break

            # --- Pisar na cabeça dos clones (mesma regra de cruzamento) ---
            if echo.vel_y > 0:
                pes = echo.y + PES_VISUAL
                pes_antes = pes - echo.vel_y * delta_time
                for eco_clone in ecos:
                    if not eco_clone.ativo:
                        continue
                    topo_cabeca = eco_clone.y + 5  # topo visível do corpo do clone
                    hb_clone = eco_clone.get_hitbox()
                    alinhado = (echo.x + echo.width - 15) > hb_clone.left and (echo.x + 15) < hb_clone.right
                    if alinhado and pes_antes <= topo_cabeca + 6 and pes >= topo_cabeca:
                        echo.y = topo_cabeca - PES_VISUAL
                        echo.vel_y = 0
                        echo.no_chao = True
                        break

            # --- Movimento e reprodução ---
            echo.mover(teclado, delta_time)
            echo.atualizar_gravacao()
            for eco in ecos:
                eco.reproduzir()

            # --- Sentinelas: gerenciam o próprio cooldown ---
            for sent in fase["sentinelas"]:
                sent.atualizar(delta_time, lasers)

            # --- Lasers: movimento e colisões (hitbox visível) ---
            echo_morreu = False
            for las in lasers:
                las.mover(delta_time)
                hit_laser = las.get_hitbox()

                # 1) Laser x Echo principal → morte, reseta a fase
                if hit_laser.colliderect(echo.get_hitbox(margem=4)):
                    echo_morreu = True
                    break

                # 2) Laser x Clone → o clone absorve o tiro e o
                #    laser some, protegendo o jogador.
                for eco in ecos:
                    if eco.ativo and hit_laser.colliderect(eco.get_hitbox(margem=0)):
                        las.ativo = False
                        break

                # 3) Laser saiu da tela
                if las.fora_da_tela():
                    las.ativo = False

            if echo_morreu:
                resetar_fase()
            else:
                lasers = [l for l in lasers if l.ativo]

            # --- Coletáveis: os 3 cubos destravam o portal ---
            for col in fase["coletaveis"]:
                if not col.coletado and echo.get_hitbox().colliderect(col.get_hitbox()):
                    col.coletado = True
            cubos_pegos = sum(1 for c in fase["coletaveis"] if c.coletado)
            cubos_total = len(fase["coletaveis"])
            portal_aberto = cubos_pegos >= cubos_total

            # --- Renderização ---
            fase["portal"].draw()
            for plat in fase["plataformas"]:
                plat.draw()
            for col in fase["coletaveis"]:
                col.draw()
            for sent in fase["sentinelas"]:
                sent.draw()
            for las in lasers:
                las.draw()
            for eco in ecos:
                eco.draw()
            echo.draw()

            # --- HUD ---
            clones_restantes = limite_clones - len(ecos)
            janela.draw_text(f"Clones Disp: {clones_restantes} / {limite_clones}", 20, 20, size=28, color=(0, 255, 255), bold=True)
            cor_cubos = (0, 255, 100) if portal_aberto else (255, 200, 0)
            janela.draw_text(f"Cubos: {cubos_pegos} / {cubos_total}", 20, 55, size=28, color=cor_cubos, bold=True)
            janela.draw_text(f"Fase {fase_atual}", 20, 90, size=24, color=(255, 255, 255), bold=True)
            if echo.gravando:
                janela.draw_text("REC", 20, 120, size=24, color=(255, 0, 0), bold=True)

            # Cronômetro discreto (canto superior direito)
            janela.draw_text(formatar_tempo(tempo_jogo), janela.width - 110, 20, size=22, color=(160, 160, 160))

            # --- Transição de fase (portal só abre com os 3 cubos) ---
            if echo.collided(fase["portal"]):
                if portal_aberto:
                    if fase_atual < 3:
                        carregar_fase(fase_atual + 1)
                    else:
                        tempo_final = tempo_jogo
                        nome_jogador = ""
                        estado_atual = ESTADO_NOME
                else:
                    janela.draw_text(f"PORTAL BLOQUEADO: faltam {cubos_total - cubos_pegos} cubo(s)!",
                                     janela.width / 2 - 220, 120, size=26, color=(255, 80, 80), bold=True)

        # ==================================================
        # ESTADO: DIGITAÇÃO DO NOME (fim de jogo)
        # ==================================================
        elif estado_atual == ESTADO_NOME:
            # Entrada de texto lida direto dos eventos do pygame
            # (a PPlay usa key.get_pressed, então não há conflito).
            for evento in pygame.event.get():
                if evento.type == pygame.QUIT:
                    pygame.quit()
                    return
                if evento.type == pygame.KEYDOWN:
                    if evento.key == pygame.K_RETURN:
                        if len(nome_jogador.strip()) > 0:
                            ranking = salvar_no_ranking(nome_jogador.strip(), tempo_final)
                            estado_atual = config.RANKING
                            click_cooldown = 0.3
                    elif evento.key == pygame.K_BACKSPACE:
                        nome_jogador = nome_jogador[:-1]
                    else:
                        ch = evento.unicode
                        if ch and (ch.isalnum() or ch == " ") and len(nome_jogador) < 12:
                            nome_jogador += ch

            cx = janela.width / 2
            if img_frase_final:
                img_frase_final.draw()
            else:
                janela.draw_text("JOGO COMPLETADO!", cx - 190, 160, size=42, color=(0, 255, 0), bold=True)
            janela.draw_text(f"Seu tempo: {formatar_tempo(tempo_final)}", cx - 120, 300, size=30, color=(255, 255, 255), bold=True)
            janela.draw_text("Digite seu nome:", cx - 100, 370, size=26, color=(0, 255, 255))
            janela.draw_text(nome_jogador + "_", cx - 100, 415, size=32, color=(255, 255, 0), bold=True)
            janela.draw_text("[ENTER] salvar no ranking", cx - 130, 480, size=22, color=(180, 180, 180))

        # ==================================================
        # ESTADO: VITÓRIA (mantido por compatibilidade)
        # ==================================================
        elif estado_atual == config.VITORIA:
            janela.draw_text("JOGO COMPLETADO!", janela.width / 2 - 180, janela.height / 2 - 50, size=40, color=(0, 255, 0), bold=True)
            btn_voltar.draw()

            if mouse.is_button_pressed(1) and click_cooldown <= 0:
                if mouse.is_over_object(btn_voltar):
                    estado_atual = config.MENU
                    click_cooldown = 0.3

        janela.update()


if __name__ == "__main__":
    main()