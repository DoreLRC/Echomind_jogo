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
    def __init__(self, x, y):
        super().__init__("assets/botao.png", 1)
        self.set_position(x, y)
        self.rect_visual = rect_opaco(self.image)  # prato ~50x14
        self.pressionado = False
        
        # Salva a imagem original (desativada)
        self.imagem_normal = self.image
        
        # Carrega a imagem ativada (vermelha)
        try:
            self.imagem_ativado = pygame.image.load("assets/botao_ativado.png").convert_alpha()
        except:
            # Prevenção de erro caso o arquivo não seja encontrado
            self.imagem_ativado = self.imagem_normal

    def get_hitbox(self):
        """Zona de pressão: o prato visível + uma faixa acima,
        para que pés apoiados no prato contem de forma estável."""
        rv = self.rect_visual
        return pygame.Rect(int(self.x) + rv.x, int(self.y) + rv.y - 14,
                           rv.w, rv.h + 14)

    def apoiar_em(self, y_superficie):
        """Assenta a base visível do prato numa superfície
        (linha do chão da fase ou topo de laje: plat.y + 46)."""
        self.set_position(self.x, y_superficie - self.rect_visual.bottom)

    # === NOVO MÉTODO ===
    def draw(self):
        """Troca a imagem baseada no estado antes de desenhar na tela."""
        if self.pressionado:
            self.image = self.imagem_ativado
        else:
            self.image = self.imagem_normal
            
        super().draw()


class Plataforma(Sprite):
    def __init__(self, x, y):
        super().__init__("assets/plataforma.png", 1)
        self.set_position(x, y)
        # Laje visível dentro do canvas (o PNG de 180x140 tem a
        # laje real em ~(21,46)-(159,100)). O pouso do jogador
        # usa ESTE retângulo, não o canvas com padding.
        self.rect_visual = rect_opaco(self.image)


# ==========================================================
# COLETÁVEL — cubo de dados: colete os 3 da fase para o
# portal funcionar (não dá mais clone extra)
# ==========================================================
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
# LASER — projétil disparado pela Sentinela
# ==========================================================
class Laser(Sprite):
    
    def __init__(self, x, y, direcao, velocidade=400, alcance=None, imagem="laser.png"):
        super().__init__(f"assets/{imagem}", 1) # Usa a variável de imagem agora
        self.set_position(x, y)
        self.direcao = direcao
        self.vel_x = velocidade
        # ... o resto do __init__ continua exatamente igual ...
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
        
        # Sorteio: 20% de chance (0.2) de ser o laser2.png. 
        # Você pode alterar esse 0.2 para 0.5 (50%), 0.1 (10%), etc.
        if random.random() < 0.2:
            img_escolhida = "laser2.png"
        else:
            img_escolhida = "laser.png"

        # Passamos a img_escolhida para o novo Laser
        novo = Laser(0, 0, self.direcao, self.vel_laser, self.alcance, imagem=img_escolhida)
        
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