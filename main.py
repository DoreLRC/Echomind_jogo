# main.py
from pplay.window import Window
from pplay.gameimage import GameImage
from pplay.sprite import Sprite
import config
from entidades import Echo, Eco, Portal, Plataforma, Sentinela, Laser, Coletavel, Botao, SentinelaVoadora, PlataformaMovel
import pygame
import json
import datetime

# Estados extras (não existem no config.py)
ESTADO_NOME = 5       # digitação do nome no fim do jogo
ESTADO_CUTSCENE = 6   # cutscene entre a fase 4 e a fase 5

ARQUIVO_RANKING = "ranking.json"
FASE_FINAL = 6


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
    try:
        with open(ARQUIVO_RANKING, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return sorted(dados, key=lambda r: r.get("tempo", 999999))
    except Exception:
        return []


def salvar_no_ranking(nome, tempo):
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
# LINHA DO CHÃO DE CADA FASE
# Cada fundo tem a rua/piso numa altura diferente. Se o
# boneco flutuar ou afundar numa fase, ajuste SÓ o número
# dela (px a partir do topo; maior = mais para baixo).
# ==========================================================
CHAO_FASE = {
    1: 680,   # fase1.jpg
    2: 700,   # fase2.jpg  (calçada do novo fundo)
    3: 680,   # fase3.jpg
    4: 690,   # fase4.png  (corredor de servidores)
    5: 700,   # fase5.png  (mundo branco)
    6: 650,   # fase6.png  (sala-janela: o piso é mais alto)
}

FUNDO_FASE_ARQ = {
    1: "assets/fase1.jpg", 2: "assets/fase2.jpg", 3: "assets/fase3.jpg",
    4: "assets/fase4.jpg", 5: "assets/fase5.jpg", 6: "assets/fase6.jpg",
}

PORTAL_FASE_IMG = {
    1: "portal.png", 2: "portal.png", 3: "portal.png",
    4: "portalfase4.png",          # portal VERMELHO especial → cutscene
    5: "portal_branca_.png",       # mundo branco: portal roxo
    6: "portal_branca_.png",
}


# ==========================================================
# HELPERS DE MONTAGEM
# ==========================================================
def pedestal_para(sentinela):
    """Plataforma de apoio sob uma sentinela flutuante: a laje
    visível encosta na base visível da torre."""
    p = Plataforma(0, 0)
    rv = p.rect_visual
    base_torre = sentinela.y + sentinela.rect_visual.bottom
    centro_torre = sentinela.x + sentinela.rect_visual.centerx
    p.set_position(centro_torre - rv.centerx, base_torre - rv.top)
    return p


def portal_sobre(plataforma, imagem):
    """Cria o portal com a base exatamente no topo visível da
    laje, centralizado nela (alinha em qualquer fundo/escala)."""
    p = Portal(0, 0, imagem)
    laje = plataforma.rect_visual
    topo_laje = plataforma.y + laje.top
    centro_laje = plataforma.x + laje.centerx
    p.set_position(centro_laje - p.rect_visual.centerx,
                   topo_laje - p.rect_visual.bottom)
    return p


def botao_no_chao(x, chao):
    b = Botao(x, 0)
    b.apoiar_em(chao)
    return b


def botao_na_laje(x, plataforma):
    b = Botao(x, 0)
    b.apoiar_em(plataforma.y + plataforma.rect_visual.top)
    return b


# ==========================================================
# FÁBRICA DE FASES (PUZZLES)
# ----------------------------------------------------------
# FÍSICA usada na calibragem (não mude sem recalcular):
# - Pé visual do corpo: y+105. Em pé numa laje: y = plat.y-59.
# - Pulo sobe 120px e viaja ~224px na horizontal.
# - Cabeça de clone: pisar nela dá ~100px extras de altura.
# - Corpo em pé em Y ocupa (Y+5 .. Y+105).
# - Torre visível: ESQ x+73..x+170 | DIR x+80..x+177;
#   cano em y_torre+85. Tela: -73 <= x <= 1105 p/ aparecer.
# REGRAS DO PORTAL: 3 cubos coletados E todos os botões da
# fase pressionados EM TEMPO REAL (clone segurando conta).
# ==========================================================
def criar_fase(numero):
    fase = {"portal": None, "plataformas": [], "sentinelas": [],
            "coletaveis": [], "botoes": [], "voadoras": [], "moveis": [],
            "chao": CHAO_FASE.get(numero, config.ALTURA_TELA - config.CHAO_Y_OFFSET)}
    chao = fase["chao"]
    img_portal = PORTAL_FASE_IMG.get(numero, "portal.png")

    if numero == 1:
        # ==================================================
        # FASE 1 — "O SACRIFÍCIO"
        # Corredor rasante (escudo ANDANDO) + escada com vão
        # impossível (clone-degrau) + BOTÃO no chão atrás do
        # perigo: o portal só abre com um clone-estátua
        # parado sobre ele (grave-se PARADO em cima: fita de
        # 1 posição = estátua permanente).
        # Cubos: Mirante (esq., estátua no spawn + salto na
        # linha da S3), Boca do Canhão da S2 (dir.), arco B→C.
        # Clones mínimos no Difícil: escudo, botão, degrau A,
        # mirante = 4 (exato).
        # ==================================================
        A = Plataforma(800, 575)
        B = Plataforma(950, 380)
        C = Plataforma(1090, 280)
        fase["plataformas"] = [A, B, C]
        fase["portal"] = portal_sobre(C, img_portal)

        s1 = Sentinela(620, 0, "ESQUERDA", cooldown=0.85, vel_laser=480,
                       timer_inicial=0.0, alcance=460)      # rasante; spawn seguro
        s1.apoiar_no_chao(chao)
        s2 = Sentinela(1105, 0, "ESQUERDA", cooldown=2.2, vel_laser=420, timer_inicial=1.1)
        s2.posicionar_cano_em(505)                            # anti-pulo / anti-escada
        s3 = Sentinela(-70, 0, "DIREITA", cooldown=2.4, vel_laser=400, timer_inicial=0.0)
        s3.posicionar_cano_em(410)                            # degrau B + cubos
        fase["sentinelas"] = [s1, s2, s3]
        fase["plataformas"] += [pedestal_para(s2), pedestal_para(s3)]

        fase["botoes"] = [botao_no_chao(880, chao)]

        fase["coletaveis"] = [
            Coletavel(80, 340),      # MIRANTE (esquerda)
            Coletavel(1090, 450),    # BOCA DO CANHÃO (direita)
            Coletavel(1040, 250),    # TRAVESSIA B→C (topo)
        ]

        # + SENTINELA VOADORA (adição: nada da fase mudou).
        # Patrulha soltando tiros VERTICAIS com colunas em
        # x 759..1039: a subida A→B→C e o cubo da travessia
        # ganham uma chuva móvel — estátua não anula, a
        # coluna anda junto com o pod.
        fase["voadoras"] = [SentinelaVoadora(600, 880, 40, cooldown=1.6,
                            vel_patrulha=90, vel_laser=420,
                            y_chao=fase["chao"], timer_inicial=0.4)]

    elif numero == 2:
        # ==================================================
        # FASE 2 — "ESCALADA SINCRONIZADA"  (chão novo: 700)
        # Torre P2→P3→P4 (dois empilhamentos) + rasante SA.
        # NOVO: plataforma do BOTÃO (BJ) varrida pela SB —
        # gravar parado ali é morte: a fita PRECISA conter
        # PULOS sobre os tiros → o clone-botão fica pulando,
        # o portal solta a cada pulo e a entrada é sincronizada.
        # Cubo 1 pego saltando da própria BJ (sem clone extra).
        # Clones no Difícil: botão, escudo, P2, P3 = 4 (exato).
        # ==================================================
        P2 = Plataforma(620, 545)
        P3 = Plataforma(820, 345)
        P4 = Plataforma(1080, 150)
        BJ = Plataforma(330, 540)    # plataforma do botão
        fase["plataformas"] = [P2, P3, P4, BJ]
        fase["portal"] = portal_sobre(P4, img_portal)

        sa = Sentinela(1105, 0, "ESQUERDA", cooldown=0.95, vel_laser=480,
                       timer_inicial=0.0, alcance=720)       # rasante; spawn seguro
        sa.apoiar_no_chao(chao)
        sb = Sentinela(1105, 0, "ESQUERDA", cooldown=2.0, vel_laser=420, timer_inicial=0.7)
        sb.posicionar_cano_em(490)   # varre BJ, cabeça-de-clone em P2 e quem descansa em P2
        sc = Sentinela(-70, 0, "DIREITA", cooldown=2.4, vel_laser=400, timer_inicial=0.0)
        sc.posicionar_cano_em(250)   # cabeça do clone de P3 (salto final)
        sd = Sentinela(-70, 0, "DIREITA", cooldown=2.6, vel_laser=380, timer_inicial=1.3)
        sd.posicionar_cano_em(350)   # quem está de pé em P3
        fase["sentinelas"] = [sa, sb, sc, sd]
        fase["plataformas"] += [pedestal_para(sb), pedestal_para(sc), pedestal_para(sd)]

        fase["botoes"] = [botao_na_laje(390, BJ)]

        cubo_chao = Coletavel(1030, 0)
        cubo_chao.apoiar_no_chao(chao)
        fase["coletaveis"] = [
            Coletavel(250, 330),     # salto p/ a esquerda a partir da BJ (linha SB)
            cubo_chao,               # zona de fogo da SA (escudo)
            Coletavel(990, 230),     # arco do salto final (linha SC)
        ]

        # + SENTINELA VOADORA (adição): colunas em x 650..1050
        # sobre a torre P2/P3 — a escalada e os head-hops agora
        # dividem atenção com a chuva vertical.
        fase["voadoras"] = [SentinelaVoadora(491, 891, 30, cooldown=1.5,
                            vel_patrulha=100, vel_laser=430,
                            y_chao=fase["chao"], timer_inicial=0.0)]

    elif numero == 3:
        # ==================================================
        # FASE 3 — "A FENDA"
        # Escada TRIPLA (L1→L2→TOPO, dois clones-degrau) +
        # travessia MID→PF. Rasante SG atira p/ a DIREITA:
        # o BOTÃO fica DENTRO da zona de fogo — a primeira
        # entrada exige gravar um clone ANDANDO da zona
        # segura até parar na frente (escudo), e a estátua
        # do botão se auto-protege absorvendo os tiros.
        # Clones no Difícil: escudo, botão, L1, L2 = 4 (exato).
        # ==================================================
        L1 = Plataforma(150, 545)
        L2 = Plataforma(330, 350)
        TOPO = Plataforma(620, 180)
        MID = Plataforma(830, 260)
        PF = Plataforma(990, 380)
        fase["plataformas"] = [L1, L2, TOPO, MID, PF]
        fase["portal"] = portal_sobre(PF, img_portal)

        sg = Sentinela(560, 0, "DIREITA", cooldown=0.9, vel_laser=480,
                       timer_inicial=0.0, alcance=500)       # zona de fogo x~737..1237
        sg.apoiar_no_chao(chao)
        sh = Sentinela(1105, 0, "ESQUERDA", cooldown=2.2, vel_laser=420, timer_inicial=0.0)
        sh.posicionar_cano_em(250)   # cabeça do clone de L2 + MID + cubo da travessia
        si = Sentinela(-70, 0, "DIREITA", cooldown=2.6, vel_laser=400, timer_inicial=1.0)
        si.posicionar_cano_em(140)   # TOPO + cubo do Pico
        sj = Sentinela(1105, 0, "ESQUERDA", cooldown=2.4, vel_laser=410, timer_inicial=1.2)
        sj.posicionar_cano_em(420)   # cabeça do clone de L1 + chegada ao portal
        fase["sentinelas"] = [sg, sh, si, sj]
        fase["plataformas"] += [pedestal_para(sh), pedestal_para(si), pedestal_para(sj)]

        fase["botoes"] = [botao_no_chao(820, chao)]   # dentro do fogo da SG

        cubo_chao = Coletavel(1050, 0)
        cubo_chao.apoiar_no_chao(chao)
        fase["coletaveis"] = [
            Coletavel(660, 60),      # PICO (linha da SI)
            cubo_chao,               # fundo da zona de fogo
            Coletavel(760, 190),     # abismo da travessia (linha da SH)
        ]

        # + SENTINELA VOADORA (adição): colunas em x 700..1050
        # sobre a travessia TOPO→MID→PF e a chegada ao portal.
        fase["voadoras"] = [SentinelaVoadora(541, 891, 25, cooldown=1.6,
                            vel_patrulha=95, vel_laser=420,
                            y_chao=fase["chao"], timer_inicial=0.8)]

    elif numero == 4:
        # ==================================================
        # FASE 4 — "NÚCLEO"  (portal VERMELHO → cutscene)
        #
        # BOTÃO MÓVEL: o botão anda montado numa plataforma
        # móvel (vaivém 520↔760). Estátua NÃO segura: o botão
        # sai de baixo dela. Só segura uma fita gravada
        # ANDANDO JUNTO com a plataforma, spawnada (Q) na
        # fase certa do vaivém — embarque pela Q1, cronometrado.
        # Escada dupla Q1→Q2→Q3, SALTO COMPROMETIDO de 212px
        # até o portal (varrido pela SL) e voadora chovendo
        # sobre o corredor do trem e a torre.
        # Clones no Difícil: fita-do-trem, Q1, Q2, escudo = 4.
        # ==================================================
        Q1 = Plataforma(180, 530)
        Q2 = Plataforma(430, 340)
        Q3 = Plataforma(700, 200)
        QP = Plataforma(1050, 320)   # plataforma do portal
        MB = PlataformaMovel(520, 470, 760, 470, velocidade=120)  # o "trem"
        fase["plataformas"] = [Q1, Q2, Q3, QP, MB]
        fase["moveis"] = [MB]
        fase["portal"] = portal_sobre(QP, img_portal)

        sk = Sentinela(1105, 0, "ESQUERDA", cooldown=0.9, vel_laser=480,
                       timer_inicial=0.0, alcance=700)       # rasante; spawn seguro
        sk.apoiar_no_chao(chao)
        sl = Sentinela(1105, 0, "ESQUERDA", cooldown=2.3, vel_laser=420, timer_inicial=1.0)
        sl.posicionar_cano_em(300)   # varre a chegada ao portal (QP)
        sn = Sentinela(-70, 0, "DIREITA", cooldown=2.2, vel_laser=400, timer_inicial=0.0)
        sn.posicionar_cano_em(160)   # varre Q3 e o salto comprometido
        sp = Sentinela(1105, 0, "ESQUERDA", cooldown=2.3, vel_laser=410, timer_inicial=0.6)
        sp.posicionar_cano_em(260)   # cabeça do clone de Q2
        fase["sentinelas"] = [sk, sl, sn, sp]
        fase["plataformas"] += [pedestal_para(sl), pedestal_para(sn), pedestal_para(sp)]

        # Voadora: colunas em x 459..919 (torre + corredor do trem)
        fase["voadoras"] = [SentinelaVoadora(300, 760, 30, cooldown=1.4,
                            vel_patrulha=105, vel_laser=440,
                            y_chao=chao, timer_inicial=0.0)]

        bot_trem = Botao(0, 0)
        bot_trem.montura = MB        # o botão viaja com o trem
        fase["botoes"] = [bot_trem]

        cubo_chao = Coletavel(1080, 0)
        cubo_chao.apoiar_no_chao(chao)
        fase["coletaveis"] = [
            Coletavel(920, 120),     # vão Q3→QP (salto comprometido, linha SN)
            cubo_chao,               # fundo da zona de fogo da SK
            Coletavel(640, 330),     # CUBO DO TREM: pulo a partir da plataforma móvel
        ]

    elif numero == 5:
        # ==================================================
        # FASE 5 — "MUNDO BRANCO"  (pós-cutscene)
        #
        # Invertida (progresso p/ a ESQUERDA) e agora com
        # ELEVADOR: a plataforma do botão BB ficou alta demais
        # para pular — só se chega de carona no elevador
        # vertical (860: 540↔390) e saltando no topo do curso.
        # DOIS botões (BB no alto + BB2 no meio do fogo) +
        # torre W1→W2→W3 + voadora varrendo a escalada e a
        # chegada: no Difícil os 4 clones fecham exatos
        # (W1, W2, BB, BB2) — zero folga, cada morte custa caro.
        # ==================================================
        W1 = Plataforma(900, 565)
        W2 = Plataforma(650, 360)
        W3 = Plataforma(380, 170)
        WP = Plataforma(90, 290)     # plataforma do portal (alto-esquerda)
        BB = Plataforma(1050, 380)   # plataforma do botão (ALTA: só via elevador)
        ME = PlataformaMovel(860, 540, 860, 390, velocidade=90)  # elevador
        fase["plataformas"] = [W1, W2, W3, WP, BB, ME]
        fase["moveis"] = [ME]
        fase["portal"] = portal_sobre(WP, img_portal)

        sr = Sentinela(200, 0, "DIREITA", cooldown=0.85, vel_laser=480,
                       timer_inicial=0.0, alcance=500)       # fogo no MEIO (x~377..877)
        sr.apoiar_no_chao(chao)
        ss = Sentinela(1105, 0, "ESQUERDA", cooldown=2.1, vel_laser=420,
                       timer_inicial=0.5, alcance=150)       # queima-roupa na BB
        ss.posicionar_cano_em(380)
        st = Sentinela(-70, 0, "DIREITA", cooldown=2.4, vel_laser=400, timer_inicial=0.0)
        st.posicionar_cano_em(250)   # cabeça do clone de W2
        su = Sentinela(1105, 0, "ESQUERDA", cooldown=2.3, vel_laser=390, timer_inicial=1.2)
        su.posicionar_cano_em(130)   # W3 + salto final para o portal
        fase["sentinelas"] = [sr, ss, st, su]
        fase["plataformas"] += [pedestal_para(ss), pedestal_para(st), pedestal_para(su)]

        # Voadora: colunas em x 200..800 (escalada + canto do portal)
        fase["voadoras"] = [SentinelaVoadora(41, 641, 25, cooldown=1.5,
                            vel_patrulha=100, vel_laser=430,
                            y_chao=chao, timer_inicial=0.3)]

        bb2 = Botao(600, 0)
        bb2.apoiar_em(chao)          # no meio da zona de fogo
        fase["botoes"] = [botao_na_laje(1110, BB), bb2]

        cubo_chao = Coletavel(500, 0)
        cubo_chao.apoiar_no_chao(chao)
        fase["coletaveis"] = [
            Coletavel(230, 90),      # vão W3→WP (linha SU)
            cubo_chao,               # zona de fogo central
            Coletavel(1080, 250),    # acima da BB (salto no alto do elevador)
        ]

    elif numero == 6:
        # ==================================================
        # FASE 6 — "SINGULARIDADE"  (final)
        #
        # TRÊS botões, três fitas inteligentes:
        #  - BOTÃO-TREM montado na plataforma móvel MF
        #    (480↔720, sobre a zona de fogo): fita cavalgante
        #    spawnada na fase certa do vaivém;
        #  - PAR DE PATRULHA (600 e 780, com retenção de 1.2s):
        #    UMA fita andando entre os dois segura ambos —
        #    duas estátuas custariam 2 clones e ESTOURAM o
        #    limite do Difícil: a patrulha é obrigatória.
        # Escada X1→X2→X3, travessia XMID→XP varrida (SW/SV),
        # voadora cobrindo o meio do mapa inteiro.
        # Clones no Difícil: trem, patrulha, X1, X2 = 4 exatos.
        # ==================================================
        X1 = Plataforma(150, 500)
        X2 = Plataforma(360, 310)
        X3 = Plataforma(640, 170)
        XMID = Plataforma(850, 210)
        XP = Plataforma(1070, 290)   # plataforma do portal
        MF = PlataformaMovel(480, 430, 720, 430, velocidade=115)  # trem da fase 6
        fase["plataformas"] = [X1, X2, X3, XMID, XP, MF]
        fase["moveis"] = [MF]
        fase["portal"] = portal_sobre(XP, img_portal)

        sy = Sentinela(250, 0, "DIREITA", cooldown=0.85, vel_laser=480,
                       timer_inicial=0.0, alcance=450)       # zona de fogo x~427..877
        sy.apoiar_no_chao(chao)
        sw = Sentinela(1105, 0, "ESQUERDA", cooldown=2.0, vel_laser=410, timer_inicial=1.1)
        sw.posicionar_cano_em(200)   # varre X3 e XMID
        sv = Sentinela(1105, 0, "ESQUERDA", cooldown=2.4, vel_laser=400,
                       timer_inicial=0.4, alcance=300)       # chegada ao portal (poupa X2/trem)
        sv.posicionar_cano_em(300)
        fase["sentinelas"] = [sy, sw, sv]
        fase["plataformas"] += [pedestal_para(sw), pedestal_para(sv)]

        # Voadora: colunas em x 409..1009 (fogo + trem + travessia)
        fase["voadoras"] = [SentinelaVoadora(250, 850, 20, cooldown=1.35,
                            vel_patrulha=110, vel_laser=440,
                            y_chao=chao, timer_inicial=0.0)]

        bot_trem = Botao(0, 0)
        bot_trem.montura = MF
        b_pat1 = Botao(600, 0, retencao=1.2)
        b_pat1.apoiar_em(chao)
        b_pat2 = Botao(780, 0, retencao=1.2)
        b_pat2.apoiar_em(chao)
        fase["botoes"] = [bot_trem, b_pat1, b_pat2]

        cubo_chao = Coletavel(480, 0)
        cubo_chao.apoiar_no_chao(chao)
        fase["coletaveis"] = [
            Coletavel(770, 100),     # vão X3→XMID (linha SW)
            cubo_chao,               # borda da zona de fogo
            Coletavel(560, 290),     # CUBO DO TREM da fase 6
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
    fundos = {}
    for num, arq in FUNDO_FASE_ARQ.items():
        try:
            g = GameImage(arq)
            g.image = pygame.transform.smoothscale(g.image, (janela.width, janela.height))
            fundos[num] = g
        except Exception:
            fundos[num] = None

    # Fundo da tela de finalização
    try:
        fundo_final = GameImage("assets/telafinal.jpg")
        fundo_final.image = pygame.transform.smoothscale(fundo_final.image, (janela.width, janela.height))
    except:
        fundo_final = None

    # Arte do "JOGO COMPLETADO"
    try:
        img_frase_final = Sprite("assets/frasefinal.png")
        img_frase_final.set_position(janela.width / 2 - img_frase_final.width / 2, 60)
    except:
        img_frase_final = None

    # Tela de carregamento da cutscene (pisca sobre fundo preto)
    try:
        img_carregando = Sprite("assets/teladecarregamento.png")
        img_carregando.set_position(janela.width / 2 - img_carregando.width / 2,
                                    janela.height / 2 - img_carregando.height / 2)
    except:
        img_carregando = None

    # === FUNDO ANIMADO DO MENU (frame_000000.jpg .. frame_000150.jpg) ===
    frames_menu = []
    try:
        print("Carregando vídeo do menu... Aguarde.")
        for i in range(151):
            frames_menu.append(GameImage(f"assets/menu_frames/frame_{i:06d}.jpg"))
        print("Vídeo do menu carregado!")
    except Exception as e:
        print(f"Aviso: Não achou os frames do menu. Erro: {e}")
        frames_menu = []

    # === CUTSCENE (entre a fase 4 e a fase 5) ===
    frames_cutscene = []
    try:
        print("Carregando cutscene... Aguarde.")
        for i in range(151):
            frames_cutscene.append(GameImage(f"assets/cutscene/frame_{i:06d}.jpg"))
        print("Cutscene carregada!")
    except Exception as e:
        print(f"Aviso: Não achou os frames da cutscene. Erro: {e}")
        frames_cutscene = []

    frame_atual = 0
    tempo_frame = 0
    cut_frame = 0
    cut_timer = 0.0
    cut_fase = "PRE"        # PRE (carregando) -> VIDEO -> POS (carregando)
    cut_fase_timer = 0.0

    # === TÍTULO E BOTÕES DO MENU ===
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
    fundo_ativo = fundos.get(1)
    click_cooldown = 0

    limite_clones = 6    # Definido pela dificuldade

    echo = Echo("echo_andando.png", 100, 100, frames=3)
    ecos = []
    lasers = []
    tecla_e = False
    tecla_q = False

    tempo_jogo = 0.0
    tempo_final = 0.0
    nome_jogador = ""
    ranking = carregar_ranking()

    fase = criar_fase(1)

    pygame.mixer.init()
    musica_tocando = None

    # ------------------------------------------------------
    def resetar_fase():
        """Reseta a fase atual inteira: posição do Echo, clones,
        lasers, cubos e timers. (O cronômetro NÃO reseta.)"""
        echo.set_position(100, fase["chao"] - echo.height)
        echo.vel_y = 0
        echo.gravando = False
        echo.historico_acoes.clear()
        ecos.clear()
        lasers.clear()
        for col in fase["coletaveis"]:
            col.coletado = False
        for sent in fase["sentinelas"]:
            sent.timer_tiro = sent.timer_inicial
        for mov in fase["moveis"]:
            mov.resetar()
        for voa in fase["voadoras"]:
            voa.resetar()
        for bot in fase["botoes"]:
            bot.pressionado = False
            bot.carga = 0.0

    def carregar_fase(numero):
        nonlocal fase, fase_atual, fundo_ativo
        fase_atual = numero
        fase = criar_fase(numero)
        fundo_ativo = fundos.get(numero)
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
        elif estado_atual == ESTADO_CUTSCENE:
            janela.set_background_color((0, 0, 0))
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
            if musica_tocando != "MENU":
                try:
                    pygame.mixer.music.load("assets/som_menu.ogg")
                    pygame.mixer.music.set_volume(0.1)
                    pygame.mixer.music.play(-1)
                    musica_tocando = "MENU"
                except Exception as e:
                    print("Não achou o som do menu:", e)
                    musica_tocando = "ERRO"

        elif estado_atual == config.JOGANDO:
            if musica_tocando != "FASE":
                try:
                    pygame.mixer.music.load("assets/som_fase.mp3")
                    pygame.mixer.music.set_volume(0.1)
                    pygame.mixer.music.play(-1)
                    musica_tocando = "FASE"
                except Exception as e:
                    print("Não achou o som da fase:", e)
                    musica_tocando = "ERRO"

        elif estado_atual in (config.VITORIA, ESTADO_NOME, ESTADO_CUTSCENE):
            if musica_tocando != "PARADA":
                pygame.mixer.music.stop()
                musica_tocando = "PARADA"

        # ==================================================
        # ESTADO: MENU PRINCIPAL
        # ==================================================
        if estado_atual == config.MENU:
            img_titulo.draw()
            btn_jogar.draw()
            btn_ranking.draw()
            btn_sair.draw()

            # Painel de créditos (também tampa a marca d'água)
            tela = pygame.display.get_surface()
            pygame.draw.rect(tela, (8, 16, 22), (janela.width - 245, janela.height - 180, 245, 180))
            pygame.draw.rect(tela, (0, 180, 200), (janela.width - 245, janela.height - 180, 245, 180), 2)
            janela.draw_text("Feito por:", janela.width - 220, janela.height - 130, size=22, color=(0, 255, 255), bold=True)
            janela.draw_text("Kauê Lopes", janela.width - 220, janela.height - 98, size=22, color=(220, 220, 220))
            janela.draw_text("Arthur Ribeiro", janela.width - 220, janela.height - 66, size=22, color=(220, 220, 220))

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
                    tempo_jogo = 0.0
                    carregar_fase(1)

        # ==================================================
        # ESTADO: RANKING
        # ==================================================
        elif estado_atual == config.RANKING:
            janela.draw_text("RANKING DOS JOGADORES", janela.width / 2 - 190, 70, size=32, color=(255, 255, 255), bold=True)

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
        # ESTADO: CUTSCENE (fase 4 → fase 5)
        # ==================================================
        elif estado_atual == ESTADO_CUTSCENE:
            if cut_fase in ("PRE", "POS"):
                # Tela de carregamento PISCANDO sobre o fundo preto
                cut_fase_timer += delta_time
                aceso = (cut_fase_timer % 0.65) < 0.40   # 0.40s aceso / 0.25s apagado
                if aceso and img_carregando:
                    img_carregando.draw()
                duracao = 2.4 if cut_fase == "PRE" else 1.8
                if cut_fase_timer >= duracao:
                    cut_fase_timer = 0.0
                    if cut_fase == "PRE":
                        if len(frames_cutscene) == 0:
                            carregar_fase(5)
                            estado_atual = config.JOGANDO
                        else:
                            cut_fase = "VIDEO"
                            cut_frame = 0
                            cut_timer = 0.0
                    else:
                        carregar_fase(5)
                        estado_atual = config.JOGANDO
            else:
                # VÍDEO da cutscene
                frames_cutscene[cut_frame].draw()

                # Legenda "ONDE EU ESTOU?" (aparece do frame 68 ao 115)
                if 68 <= cut_frame <= 115:
                    cx = janela.width / 2
                    janela.draw_text("ONDE EU ESTOU?", cx - 146, 632, size=34, color=(0, 0, 0), bold=True)
                    janela.draw_text("ONDE EU ESTOU?", cx - 148, 630, size=34, color=(255, 255, 255), bold=True)

                cut_timer += delta_time
                if cut_timer >= 0.045:      # ~22 fps
                    cut_timer = 0.0
                    cut_frame += 1
                    if cut_frame >= len(frames_cutscene):
                        cut_fase = "POS"
                        cut_fase_timer = 0.0

        # ==================================================
        # ESTADO: JOGANDO
        # ==================================================
        elif estado_atual == config.JOGANDO:
            tempo_jogo += delta_time
            chao_y = fase["chao"] - echo.height

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

            # --- Plataformas móveis, voadoras e botões montados ---
            for mov in fase["moveis"]:
                mov.atualizar(delta_time)
            for voa in fase["voadoras"]:
                voa.atualizar(delta_time, lasers)
            for bot in fase["botoes"]:
                mont = getattr(bot, "montura", None)
                if mont is not None:
                    rvm = mont.rect_visual
                    bot.set_position(mont.x + rvm.centerx - bot.rect_visual.centerx,
                                     (mont.y + rvm.top) - bot.rect_visual.bottom)

            # --- Física do Echo ---
            echo.aplicar_gravidade(delta_time)
            echo.no_chao = False
            if echo.y >= chao_y:
                echo.y = chao_y
                echo.vel_y = 0
                echo.no_chao = True

            # --- Pouso nas plataformas (laje visível, sem teleporte) ---
            PES_VISUAL = 105
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

            # --- Pisar na cabeça dos clones ---
            if echo.vel_y > 0:
                pes = echo.y + PES_VISUAL
                pes_antes = pes - echo.vel_y * delta_time
                for eco_clone in ecos:
                    if not eco_clone.ativo:
                        continue
                    topo_cabeca = eco_clone.y + 5
                    hb_clone = eco_clone.get_hitbox()
                    alinhado = (echo.x + echo.width - 15) > hb_clone.left and (echo.x + 15) < hb_clone.right
                    if alinhado and pes_antes <= topo_cabeca + 6 and pes >= topo_cabeca:
                        echo.y = topo_cabeca - PES_VISUAL
                        echo.vel_y = 0
                        echo.no_chao = True
                        break

            # --- Carona nas plataformas móveis ---
            if echo.no_chao:
                pes_atual = echo.y + PES_VISUAL
                for mov in fase["moveis"]:
                    rvm = mov.rect_visual
                    topo_mov = mov.y + rvm.top
                    if abs(pes_atual - topo_mov) <= 8:
                        m_esq = mov.x + rvm.left + 6
                        m_dir = mov.x + rvm.right - 6
                        if (echo.x + echo.width - 15) > m_esq and (echo.x + 15) < m_dir:
                            echo.x += mov.dx_frame
                            echo.y = topo_mov - PES_VISUAL
                            break

            # --- Movimento e reprodução ---
            echo.mover(teclado, delta_time)
            echo.atualizar_gravacao()
            for eco in ecos:
                eco.reproduzir()

            # --- Sentinelas ---
            for sent in fase["sentinelas"]:
                sent.atualizar(delta_time, lasers)

            # --- Lasers ---
            echo_morreu = False
            for las in lasers:
                las.mover(delta_time)
                hit_laser = las.get_hitbox()

                if hit_laser.colliderect(echo.get_hitbox(margem=4)):
                    echo_morreu = True
                    break

                for eco in ecos:
                    if eco.ativo and hit_laser.colliderect(eco.get_hitbox(margem=0)):
                        las.ativo = False
                        break

                if las.fora_da_tela():
                    las.ativo = False

            if echo_morreu:
                # Checa se é o modo difícil pelo número limite de clones (que é 4 no modo difícil)
                if limite_clones == 4:
                    carregar_fase(1)      # Reinicia tudo voltando para a fase 1
                else:
                    resetar_fase()        # Se for fácil ou médio, reseta apenas a fase atual
            else:
                lasers = [l for l in lasers if l.ativo]

            # --- Botões: pressão em TEMPO REAL (Echo ou clone ativo) ---
            # A checagem é pelos PÉS sobre o prato (nada de ativar
            # encostando de lado). Botões com retenção (patrulha)
            # continuam "ativos" por alguns instantes após soltar.
            hb_echo = echo.get_hitbox()
            for bot in fase["botoes"]:
                apertado = bot.esta_sendo_pressionado_por(hb_echo)
                if not apertado:
                    for eco in ecos:
                        if eco.ativo and bot.esta_sendo_pressionado_por(eco.get_hitbox()):
                            apertado = True
                            break
                bot.atualizar(apertado, delta_time)

            botoes_ok = all(b.ativo() for b in fase["botoes"])

            # --- Coletáveis ---
            for col in fase["coletaveis"]:
                if not col.coletado and hb_echo.colliderect(col.get_hitbox()):
                    col.coletado = True
            cubos_pegos = sum(1 for c in fase["coletaveis"] if c.coletado)
            cubos_total = len(fase["coletaveis"])
            portal_aberto = (cubos_pegos >= cubos_total) and botoes_ok

            # --- Renderização ---
            fase["portal"].draw()
            for plat in fase["plataformas"]:
                plat.draw()
            for bot in fase["botoes"]:
                bot.draw()
            for col in fase["coletaveis"]:
                col.draw()
            for sent in fase["sentinelas"]:
                sent.draw()
            for voa in fase["voadoras"]:
                voa.draw()
            for las in lasers:
                las.draw()
            for eco in ecos:
                eco.draw()
            echo.draw()

            # --- HUD ---
            clones_restantes = limite_clones - len(ecos)
            janela.draw_text(f"Clones Disp: {clones_restantes} / {limite_clones}", 20, 20, size=28, color=(0, 255, 255), bold=True)
            cor_cubos = (0, 255, 100) if cubos_pegos >= cubos_total else (255, 200, 0)
            janela.draw_text(f"Cubos: {cubos_pegos} / {cubos_total}", 20, 55, size=28, color=cor_cubos, bold=True)
            if len(fase["botoes"]) > 0:
                n_press = sum(1 for b in fase["botoes"] if b.ativo())
                cor_bot = (0, 255, 100) if botoes_ok else (255, 80, 80)
                janela.draw_text(f"Botoes: {n_press} / {len(fase['botoes'])}", 20, 90, size=28, color=cor_bot, bold=True)
                y_fase = 125
            else:
                y_fase = 90
            janela.draw_text(f"Fase {fase_atual}", 20, y_fase, size=24, color=(255, 255, 255), bold=True)
            
            if echo.gravando:
                janela.draw_text("REC", 20, y_fase + 30, size=24, color=(255, 0, 0), bold=True)

            janela.draw_text(formatar_tempo(tempo_jogo), janela.width - 110, 20, size=22, color=(160, 160, 160))

            # --- Transição de fase ---
            if echo.collided(fase["portal"]):
                if portal_aberto:
                    if fase_atual == 4:
                        cut_fase = "PRE"
                        cut_fase_timer = 0.0
                        # Portal VERMELHO especial → cutscene → mundo branco
                        cut_frame = 0
                        cut_timer = 0.0
                        estado_atual = ESTADO_CUTSCENE
                    elif fase_atual < FASE_FINAL:
                        carregar_fase(fase_atual + 1)
                    else:
                        tempo_final = tempo_jogo
                        nome_jogador = ""
                        estado_atual = ESTADO_NOME
                else:
                    if cubos_pegos < cubos_total:
                        msg = f"PORTAL BLOQUEADO: faltam {cubos_total - cubos_pegos} cubo(s)!"
                    else:
                        msg = "PORTAL INSTAVEL: mantenha o(s) botao(oes) pressionado(s)!"
                    janela.draw_text(msg, janela.width / 2 - 260, 120, size=26, color=(255, 80, 80), bold=True)

        # ==================================================
        # ESTADO: DIGITAÇÃO DO NOME (fim de jogo)
        # ==================================================
        elif estado_atual == ESTADO_NOME:
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