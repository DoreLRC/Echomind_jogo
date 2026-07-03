class Plataforma(Sprite):
    def __init__(self, x, y):
        super().__init__("assets/plataforma.png", 1)
        self.set_position(x, y)
        # Laje visível dentro do canvas (o PNG de 180x140 tem a
        # laje real em ~(21,46)-(159,100)). O pouso do jogador
        # usa ESTE retângulo, não o canvas com padding.
        self.rect_visual = rect_opaco(self.image)