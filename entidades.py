# entidades.py
import pygame
import random
from pplay.sprite import Sprite
from pplay.window import Window
import config


# ==========================================================
# HELPERS DE HITBOX (PIXELS OPACOS)
# ----------------------------------------------------------
# Os PNGs têm muita borda transparente (a sentinela, p.ex.,
# é um canvas 250x200 mas a torre visível ocupa ~97x104).
# O collided() da PPlay usa o retângulo da IMAGEM INTEIRA,
# então o jogador "morria" antes do laser encostar de fato.
# Aqui calculamos o retângulo opaco real de cada sprite em
# tempo de execução e colidimos por ele.
# ==========================================================
def rect_opaco(surface):
    """Retângulo da área visível (alpha > 10) de uma surface."""
    try:
        r = surface.get_bounding_rect(min_alpha=10)
        if r.w > 0 and r.h > 0:
            return r
    except Exception:
        pass
    return surface.get_rect()


def _preparar_hitbox_personagem(obj):
    """Calcula o corpo visível do personagem (união dos frames
    da caminhada) e do sprite de pulo. Chamar no __init__ de
    Echo e Eco, DEPOIS de carregar imagens e definir frames."""
    folha = obj.imagem_direita
    obj.frame_largura = folha.get_width() // obj.total_frames
    altura = folha.get_height()

    uniao = None
    for i in range(obj.total_frames):
        sub = folha.subsurface((i * obj.frame_largura, 0, obj.frame_largura, altura))
        r = rect_opaco(sub)
        uniao = r.copy() if uniao is None else uniao.union(r)
    obj.corpo_andando = uniao                        # relativo ao frame
    obj.corpo_pulando = rect_opaco(obj.img_pulo_dir)  # relativo à img de pulo
    obj.largura_pulo = obj.img_pulo_dir.get_width()


def hitbox_personagem(obj, margem=0):
    """Hitbox em coordenadas de mundo, já espelhada se o
    personagem estiver virado para a esquerda."""
    if not obj.no_chao:
        base, largura_ref = obj.corpo_pulando, obj.largura_pulo
    else:
        base, largura_ref = obj.corpo_andando, obj.frame_largura

    x_rel = base.x
    if obj.direcao == "ESQUERDA":
        x_rel = largura_ref - (base.x + base.w)

    return pygame.Rect(
        int(obj.x) + x_rel + margem,
        int(obj.y) + base.y + margem,
        max(1, base.w - 2 * margem),
        max(1, base.h - 2 * margem),
    )


class Plataforma(Sprite):
    def __init__(self, x, y):
        super().__init__("assets/plataforma.png", 1)
        self.set_position(x, y)
        # Laje visível dentro do canvas (o PNG de 180x140 tem a
        # laje real em ~(21,46)-(159,100)). O pouso do jogador
        # usa ESTE retângulo, não o canvas com padding.
        self.rect_visual = rect_opaco(self.image)

class Coletavel(Sprite):
    def __init__(self, x, y):
        super().__init__("assets/coletavel.png", 1)
        self.set_position(x, y)
        self.coletado = False
        self.rect_visual = rect_opaco(self.image)

    def get_hitbox(self):
        rv = self.rect_visual
        return pygame.Rect(int(self.x) + rv.x, int(self.y) + rv.y, rv.w, rv.h)

    def apoiar_no_chao(self, chao=None):
        """Encosta a base VISÍVEL do item na linha do chão da fase."""
        if chao is None:
            chao = config.ALTURA_TELA - config.CHAO_Y_OFFSET
        self.set_position(self.x, chao - self.rect_visual.bottom)

    def draw(self):
        if not self.coletado:
            super().draw()


# ==========================================================
# ECHO — O JOGADOR PRINCIPAL
# ==========================================================
class Echo(Sprite):
    def __init__(self, image_file, x, y, frames=3):
        super().__init__(f"assets/{image_file}", frames)
        self.set_position(x, y)
        self.vel_y = 0
        self.no_chao = False
        self.direcao = "DIREITA"
        self.set_total_duration(300)

        self.gravando = False
        self.historico_acoes = []

        self.imagem_direita = self.image
        self.imagem_esquerda = pygame.transform.flip(self.image, True, False)
        self.total_frames = frames

        try:
            self.img_pulo_dir = pygame.image.load("assets/echo_pulando.png").convert_alpha()
            self.img_pulo_esq = pygame.transform.flip(self.img_pulo_dir, True, False)
        except:
            self.img_pulo_dir = pygame.Surface((int(self.width), int(self.height)))
            self.img_pulo_dir.fill((255, 0, 255))
            self.img_pulo_esq = self.img_pulo_dir

        _preparar_hitbox_personagem(self)

    def get_hitbox(self, margem=0):
        return hitbox_personagem(self, margem)

    def aplicar_gravidade(self, delta_time):
        self.vel_y += config.GRAVIDADE * delta_time
        self.y += self.vel_y * delta_time

    def mover(self, teclado, delta_time):
        movendo = False
        if teclado.key_pressed("A") or teclado.key_pressed("LEFT"):
            self.x -= config.VELOCIDADE_ECHO * delta_time
            self.direcao = "ESQUERDA"
            movendo = True
        if teclado.key_pressed("D") or teclado.key_pressed("RIGHT"):
            self.x += config.VELOCIDADE_ECHO * delta_time
            self.direcao = "DIREITA"
            movendo = True
        if (teclado.key_pressed("W") or teclado.key_pressed("SPACE") or teclado.key_pressed("UP")) and self.no_chao:
            self.vel_y = config.FORCA_PULO
            self.no_chao = False

        # Mantém o Echo dentro da tela
        if self.x < 0:
            self.x = 0
        if self.x + self.width > config.LARGURA_TELA:
            self.x = config.LARGURA_TELA - self.width

        if movendo and self.no_chao:
            self.update()
        elif self.no_chao:
            self.set_curr_frame(0)

    def atualizar_gravacao(self):
        if self.gravando:
            self.historico_acoes.append((self.x, self.y, self.direcao, self.get_curr_frame(), self.no_chao))

    def draw(self):
        if not self.no_chao:
            tela = Window.get_screen()
            if self.direcao == "ESQUERDA":
                tela.blit(self.img_pulo_esq, (int(self.x), int(self.y)))
            else:
                tela.blit(self.img_pulo_dir, (int(self.x), int(self.y)))
        elif self.direcao == "ESQUERDA":
            self.image = self.imagem_esquerda
            frame_original = self.get_curr_frame()
            frame_invertido = (self.total_frames - 1) - int(frame_original)
            frame_invertido = max(0, min(frame_invertido, self.total_frames - 1))
            self.set_curr_frame(frame_invertido)
            super().draw()
            self.image = self.imagem_direita
            self.set_curr_frame(frame_original)
        else:
            super().draw()


# ==========================================================
# ECO — O CLONE QUE REPETE A GRAVAÇÃO
# ==========================================================
class Eco(Sprite):
    def __init__(self, image_file, historico, frames=3):
        super().__init__(f"assets/{image_file}", frames)

        self.fita = list(historico)

        # Corta o "tempo morto": apaga frames parados do início da
        # gravação para o clone arrancar assim que nasce.
        while len(self.fita) > 1:
            x_atual, y_atual = self.fita[0][0], self.fita[0][1]
            x_prox, y_prox = self.fita[1][0], self.fita[1][1]
            if x_atual == x_prox and y_atual == y_prox:
                self.fita.pop(0)
            else:
                break

        self.frame_atual = 0
        self.ativo = True
        self.direcao = "DIREITA"
        self.total_frames = frames
        self.no_chao = True

        self.imagem_direita = self.image
        self.imagem_esquerda = pygame.transform.flip(self.image, True, False)

        try:
            self.img_pulo_dir = pygame.image.load("assets/echo_pulando.png").convert_alpha()
            self.img_pulo_esq = pygame.transform.flip(self.img_pulo_dir, True, False)
        except:
            self.img_pulo_dir = pygame.Surface((int(self.width), int(self.height)))
            self.img_pulo_dir.fill((255, 0, 255))
            self.img_pulo_esq = self.img_pulo_dir

        _preparar_hitbox_personagem(self)

        if len(self.fita) > 0:
            self.set_position(self.fita[0][0], self.fita[0][1])

    def get_hitbox(self, margem=0):
        return hitbox_personagem(self, margem)

    def reproduzir(self):
        if not self.ativo or len(self.fita) == 0:
            return

        x, y, direcao, frame, no_chao = self.fita[self.frame_atual]

        self.x = x
        self.y = y
        self.set_position(x, y)  # Obriga a PPlay a atualizar a caixa de colisão

        self.direcao = direcao
        self.set_curr_frame(frame)
        self.no_chao = no_chao

        self.frame_atual += 1
        if self.frame_atual >= len(self.fita):
            self.frame_atual = 0  # Loop infinito

    def draw(self):
        if not self.ativo:
            return
        if not self.no_chao:
            tela = Window.get_screen()
            if self.direcao == "ESQUERDA":
                tela.blit(self.img_pulo_esq, (int(self.x), int(self.y)))
            else:
                tela.blit(self.img_pulo_dir, (int(self.x), int(self.y)))
        elif self.direcao == "ESQUERDA":
            self.image = self.imagem_esquerda
            frame_original = self.get_curr_frame()
            frame_invertido = (self.total_frames - 1) - int(frame_original)
            frame_invertido = max(0, min(frame_invertido, self.total_frames - 1))
            self.set_curr_frame(frame_invertido)
            super().draw()
            self.image = self.imagem_direita
            self.set_curr_frame(frame_original)
        else:
            super().draw()


# ==========================================================
# CENÁRIO
# ==========================================================
class Portal(Sprite):
    def __init__(self, x, y, imagem="portal.png"):
        super().__init__(f"assets/{imagem}", 1)
        self.set_position(x, y)
        self.rect_visual = rect_opaco(self.image)


# ==========================================================
# BOTÃO — placa de pressão: só conta como pressionado
# enquanto UM CORPO (Echo ou clone ativo) estiver sobre ele
# EM TEMPO REAL. Clones em loop soltam o botão nos trechos
# da fita em que saem de cima dele.
# ==========================================================
# ==========================================================
# BOTÃO — placa de pressão: só conta como pressionado
# enquanto UM CORPO (Echo ou clone ativo) estiver sobre ele
# EM TEMPO REAL. Clones em loop soltam o botão nos trechos
# da fita em que saem de cima dele.
# ==========================================================
class Botao(Sprite):
    def __init__(self, x, y, retencao=0.0):
        super().__init__("assets/botao.png", 1)
        self.set_position(x, y)
        self.rect_visual = rect_opaco(self.image)  # prato ~50x14
        self.pressionado = False   # alguém em cima AGORA (visual vermelho)
        self.retencao = retencao   # segundos que a "carga" dura após soltar
        self.carga = 0.0

        # Versão ATIVADA (vermelha). O canvas dela é diferente
        # (80x110 vs 70x60), então alinhamos pelo desenho:
        # mesmo centro-x e mesma base do prato.
        try:
            self.img_ativado = pygame.image.load("assets/botao_ativado.png").convert_alpha()
            rv_a = rect_opaco(self.img_ativado)
            self.off_ativado = (self.rect_visual.centerx - rv_a.centerx,
                                self.rect_visual.bottom - rv_a.bottom)
        except Exception:
            self.img_ativado = None
            self.off_ativado = (0, 0)

    def prato(self):
        rv = self.rect_visual
        return pygame.Rect(int(self.x) + rv.x, int(self.y) + rv.y, rv.w, rv.h)

    def esta_sendo_pressionado_por(self, hitbox_corpo):
        """Pressão PRECISA: o centro dos pés precisa estar SOBRE o
        prato (na horizontal) e os pés na altura do prato. Encostar
        de lado não conta mais."""
        p = self.prato()
        if not (p.left <= hitbox_corpo.centerx <= p.right):
            return False
        pes = hitbox_corpo.bottom
        return (p.top - 18) <= pes <= (p.bottom + 6)

    def atualizar(self, pressionado_agora, delta_time):
        self.pressionado = pressionado_agora
        if pressionado_agora:
            self.carga = self.retencao
        elif self.carga > 0:
            self.carga -= delta_time

    def ativo(self):
        """Conta para o portal: pressão direta OU carga residual
        (usada nos pares de botões de patrulha)."""
        return self.pressionado or self.carga > 0

    def apoiar_em(self, y_superficie):
        """Assenta a base visível do prato numa superfície."""
        self.set_position(self.x, y_superficie - self.rect_visual.bottom)

    def draw(self):
        if self.pressionado and self.img_ativado is not None:
            tela = Window.get_screen()
            tela.blit(self.img_ativado,
                      (int(self.x + self.off_ativado[0]), int(self.y + self.off_ativado[1])))
        else:
            super().draw()


# ==========================================================
# LASER — projétil disparado pela Sentinela
# ==========================================================
class Laser(Sprite):
    def __init__(self, x, y, direcao, velocidade=400, alcance=None):
        super().__init__("assets/laser.png", 1)
        self.set_position(x, y)
        self.direcao = direcao
        self.vel_x = velocidade
        self.ativo = True
        # Alcance máximo em px (None = atravessa a tela toda).
        # Usado para criar zonas seguras, como o ponto de spawn.
        self.alcance = alcance
        self.x_inicial = None  # capturado no 1º mover (após o
                               # reposicionamento feito pela Sentinela)

        # A arte original do laser aponta para a ESQUERDA.
        if self.direcao == "DIREITA":
            self.image = pygame.transform.flip(self.image, True, False)

        # Área visível calculada DEPOIS do flip.
        self.rect_visual = rect_opaco(self.image)

    def get_hitbox(self):
        """Hitbox pelo desenho real do projétil, com uma folga
        interna para a morte só acontecer no toque visível."""
        rv = self.rect_visual
        mx = max(1, int(rv.w * 0.15))
        my = max(1, int(rv.h * 0.20))
        return pygame.Rect(
            int(self.x) + rv.x + mx,
            int(self.y) + rv.y + my,
            max(1, rv.w - 2 * mx),
            max(1, rv.h - 2 * my),
        )

    def mover(self, delta_time):
        if not self.ativo:
            return
        if self.x_inicial is None:
            self.x_inicial = self.x
        if self.direcao == "ESQUERDA":
            self.x -= self.vel_x * delta_time
        else:
            self.x += self.vel_x * delta_time
        if self.alcance is not None and abs(self.x - self.x_inicial) >= self.alcance:
            self.ativo = False

    def fora_da_tela(self):
        return self.x + self.width < -50 or self.x > config.LARGURA_TELA + 50


# ==========================================================
# SENTINELA — torre fixa que dispara lasers com cooldown
# ==========================================================
class Sentinela(Sprite):
    # Fração da altura VISÍVEL da torre onde fica o cano
    # (os canos ficam na parte de cima da cabeça da torre).
    FRACAO_CANO_Y = 0.33

    def __init__(self, x, y, direcao="ESQUERDA", cooldown=1.5, vel_laser=400, timer_inicial=0.0, alcance=None):
        super().__init__("assets/sentinela.png", 1)
        self.set_position(x, y)
        self.direcao = direcao
        self.cooldown = cooldown
        self.vel_laser = vel_laser
        # Alcance máximo dos lasers desta torre (None = tela toda)
        self.alcance = alcance
        # timer_inicial dessincroniza torres com o mesmo cooldown,
        # criando padrões de tiro intercalados (mais difíceis).
        self.timer_inicial = timer_inicial
        self.timer_tiro = timer_inicial

        # A arte original da sentinela aponta para a DIREITA.
        if self.direcao == "ESQUERDA":
            self.image = pygame.transform.flip(self.image, True, False)

        # Torre visível dentro do canvas (calculada após o flip).
        self.rect_visual = rect_opaco(self.image)

    def apoiar_no_chao(self, chao=None):
        """Encosta a BASE VISÍVEL da torre na linha do chão.
        `chao` permite usar a linha específica da fase (cada
        fundo tem a rua numa altura diferente)."""
        if chao is None:
            chao = config.ALTURA_TELA - config.CHAO_Y_OFFSET
        self.set_position(self.x, chao - self.rect_visual.bottom)

    def posicionar_cano_em(self, y_cano):
        """Posiciona a torre para que o CANO fique exatamente na
        altura y_cano (pixels de mundo). Útil para desenhar
        corredores de tiro precisos nos puzzles."""
        tv = self.rect_visual
        self.set_position(self.x, y_cano - (tv.y + tv.h * self.FRACAO_CANO_Y))

    def atualizar(self, delta_time, lista_lasers):
        """Gerencia o tempo entre disparos usando delta_time."""
        self.timer_tiro += delta_time
        if self.timer_tiro >= self.cooldown:
            self.timer_tiro = 0
            self.atirar(lista_lasers)

    def atirar(self, lista_lasers):
        """Cria o laser exatamente na boca do cano VISÍVEL da
        torre — e não no canto do canvas transparente, que era o
        que fazia o tiro nascer 'no chão, na frente da sentinela'."""
        novo = Laser(0, 0, self.direcao, self.vel_laser, self.alcance)
        lv = novo.rect_visual
        tv = self.rect_visual

        # Altura do cano no mundo
        y_cano = self.y + tv.y + tv.h * self.FRACAO_CANO_Y

        # Centraliza o desenho do laser na altura do cano
        novo_y = y_cano - lv.centery

        if self.direcao == "ESQUERDA":
            # Borda visível DIREITA do laser nasce encostada na
            # borda visível ESQUERDA da torre (leve sobreposição).
            novo_x = (self.x + tv.left) - lv.right + 8
        else:
            novo_x = (self.x + tv.right) - lv.left - 8

        novo.set_position(novo_x, novo_y)
        lista_lasers.append(novo)

# ==========================================================
# LASER VERTICAL — tiro da sentinela voadora (laser2.png).
# A arte aponta p/ a direita; rotacionamos p/ apontar p/ BAIXO.
# Hitbox maior e o projétil morre só ao tocar o chão da fase.
# ==========================================================
class LaserVertical(Sprite):
    def __init__(self, x, y, velocidade=430, y_max=720):
        super().__init__("assets/laser2.png", 1)
        self.image = pygame.transform.rotate(self.image, -90)  # aponta p/ baixo
        self.set_position(x, y)
        self.vel_y = velocidade
        self.y_max = y_max          # linha do chão da fase
        self.ativo = True
        self.direcao = "BAIXO"
        self.rect_visual = rect_opaco(self.image)  # ~14x70 após rotação

    def get_hitbox(self):
        rv = self.rect_visual
        mx = max(1, int(rv.w * 0.10))
        my = max(1, int(rv.h * 0.08))
        return pygame.Rect(int(self.x) + rv.x + mx, int(self.y) + rv.y + my,
                           max(1, rv.w - 2 * mx), max(1, rv.h - 2 * my))

    def mover(self, delta_time):
        if not self.ativo:
            return
        self.y += self.vel_y * delta_time
        # morre quando a PONTA visível alcança o chão
        if self.y + self.rect_visual.bottom >= self.y_max:
            self.ativo = False

    def fora_da_tela(self):
        return self.y > config.ALTURA_TELA + 60


# ==========================================================
# SENTINELA VOADORA — patrulha horizontal soltando tiros
# VERTICAIS (sentinela2.png). Uma chuva móvel: estátuas não
# a anulam, porque a coluna de tiro anda com ela.
# ==========================================================
class SentinelaVoadora(Sprite):
    def __init__(self, x_min, x_max, y, cooldown=1.5, vel_patrulha=100,
                 vel_laser=430, y_chao=720, timer_inicial=0.0):
        super().__init__("assets/sentinela2.png", 1)
        self.x_min = x_min
        self.x_max = x_max
        self.x_inicial = x_min
        self.set_position(x_min, y)
        self.cooldown = cooldown
        self.vel_patrulha = vel_patrulha
        self.vel_laser = vel_laser
        self.y_chao = y_chao
        self.timer_inicial = timer_inicial
        self.timer_tiro = timer_inicial
        self.sentido = 1
        self.rect_visual = rect_opaco(self.image)  # pod ~68x155

    def resetar(self):
        self.set_position(self.x_inicial, self.y)
        self.sentido = 1
        self.timer_tiro = self.timer_inicial

    def atualizar(self, delta_time, lista_lasers):
        # patrulha ping-pong
        self.x += self.vel_patrulha * self.sentido * delta_time
        if self.x >= self.x_max:
            self.x = self.x_max
            self.sentido = -1
        elif self.x <= self.x_min:
            self.x = self.x_min
            self.sentido = 1
        self.set_position(self.x, self.y)

        # tiro vertical saindo da BASE do pod, centralizado
        self.timer_tiro += delta_time
        if self.timer_tiro >= self.cooldown:
            self.timer_tiro = 0
            novo = LaserVertical(0, 0, self.vel_laser, self.y_chao)
            lv = novo.rect_visual
            tv = self.rect_visual
            novo.set_position(self.x + tv.centerx - lv.centerx,
                              self.y + tv.bottom - lv.top - 6)
            lista_lasers.append(novo)


# ==========================================================
# PLATAFORMA MÓVEL — vai e volta entre dois pontos. O Echo é
# CARREGADO por ela; clones NÃO (fitas guardam posições
# absolutas) — por isso um botão montado nela só pode ser
# segurado por uma fita gravada ANDANDO JUNTO, spawnada na
# fase certa do vaivém.
# ==========================================================
class PlataformaMovel(Plataforma):
    def __init__(self, x1, y1, x2, y2, velocidade=100):
        super().__init__(x1, y1)
        self.p1 = (x1, y1)
        self.p2 = (x2, y2)
        self.velocidade = velocidade
        self.indo = True          # True: rumo a p2
        self.dx_frame = 0.0
        self.dy_frame = 0.0

    def resetar(self):
        self.set_position(*self.p1)
        self.indo = True
        self.dx_frame = self.dy_frame = 0.0

    def atualizar(self, delta_time):
        alvo = self.p2 if self.indo else self.p1
        vx = alvo[0] - self.x
        vy = alvo[1] - self.y
        dist = (vx * vx + vy * vy) ** 0.5
        passo = self.velocidade * delta_time
        if dist <= passo or dist == 0:
            self.dx_frame = alvo[0] - self.x
            self.dy_frame = alvo[1] - self.y
            self.set_position(alvo[0], alvo[1])
            self.indo = not self.indo
        else:
            self.dx_frame = vx / dist * passo
            self.dy_frame = vy / dist * passo
            self.set_position(self.x + self.dx_frame, self.y + self.dy_frame)


