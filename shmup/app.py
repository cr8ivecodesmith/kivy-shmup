import pdb
import math
import json
from random import randint, random
from collections import namedtuple

from kivy.app import App
from kivy.core.image import Image
from kivy.core.window import Window
from kivy.base import EventLoop
from kivy.clock import Clock
from kivy.graphics import Mesh
from kivy.graphics.instructions import RenderContext
from kivy.uix.widget import Widget


UVMapping = namedtuple('UVMapping', 'u0 v0 u1 v1 su sv')
""" Universal value holder for sprites

u0, v0 - Coords of the sprite's top-left corner
u1, v1 - Coords of the sprite's bottom-right corner
su - Sprite width divided by 2; useful when building array of vertices
sv - Sprite height divided by 2

"""


def load_atlas(atlas_name):
    with open(atlas_name, 'rb') as fh:
        atlas = json.loads(fh.read().decode('utf-8'))
        tex_name, mapping = atlas.popitem()

        # We might have to find the abs location of the image if its in a diff.
        # location than this file.
        tex = Image('assets/images/' + tex_name).texture
        tex_width, tex_height = tex.size

        uvmap = {}
        for name, val in mapping.items():
            x0, y0, w, h = val
            x1, y1 = x0 + w, y0 + h
            uvmap[name] = UVMapping(
                x0 / tex_width, 1 - y1 /tex_height,
                x1 / tex_width, 1 - y0 /tex_height,
                0.5 * w, 0.5 * h
            )

        return tex, uvmap


class PSWidget(Widget):
    """ Abstract class to handle all sprite rendering

    An instance of this renderer will only hold a single source of texture.

    """
    indices = []
    vertices = []
    particles = []

    def __init__(self, **kwargs):
        super(PSWidget, self).__init__(**kwargs)
        self.canvas = RenderContext(use_parent_projection=True)
        self.canvas.shader.source = self.glsl

        self.vfmt = (
            (b'vCenter', 2, 'float'),
            (b'vScale', 1, 'float'),
            (b'vPosition', 2, 'float'),
            (b'vTexCoords0', 2, 'float'),
        )

        self.vsize = sum(attr[1] for attr in self.vfmt)

        self.texture, self.uvmap = load_atlas(self.atlas)

    def make_particles(self, Cls, num):
        """ Convenience method to add a large number (`num`) of similar
        particles 


        Parameters
        ----------

        Cls (obj) - Particle class instance. This should implement a `tex_name`
            property to lookup the correct sprite in the UV mapping.

        num (int) - Number of particles to add.

        """
        count = len(self.particles)
        uv = self.uvmap[Cls.tex_name]

        for i in range(count, count + num):
            j = 4 * i
            self.indices.extend((
                j, j + 1, j + 2, j + 2, j + 3, j))
            self.vertices.extend((
                0, 0, 1, -uv.su, -uv.sv, uv.u0, uv.v1,
                0, 0, 1, uv.su, -uv.sv, uv.u1, uv.v1,
                0, 0, 1, uv.su, uv.sv, uv.u1, uv.v0,
                0, 0, 1, -uv.su, uv.sv, uv.u0, uv.v0,
            ))

            p = Cls(self, i)
            self.particles.append(p)

    def update_glsl(self, nap):
        """ Update the canvas.

        NOTES: Take the ff. into consideration when optimization is necessary:

        The particles update loop:
        - This loop should parallelized in full or partially.
        - This could also be run on another thread completely, and not update
            on every frame. This may apply to selected particle sub-classes,
            i.e. stuff in the background that doesn't affect program flow.


        Parameters
        ----------

        nap (float) - TODO

        """
        # Update the state of all particles
        for p in self.particles:
            p.advance(nap)
            p.update()

        # Draw the changes
        self.canvas.clear()
        with self.canvas:
            Mesh(fmt=self.vfmt, mode='triangles', indices=self.indices,
                 vertices=self.vertices, texture=self.texture)


class Particle(object):
    """ Component abstract class to represent all individual particles.

    Each particle is tightly-coupled to a renderer class and vice-versa. This
    improves performance such that each particle will have direct access to the
    vertices array in the renderer. This means less copying of the vertices
    array, taking into account that there could be many particles active at the
    same time.


    Parameters
    ----------

    parent (obj) - Reference to the renderer this particle belongs to.
    i (int) - Reference to this particle's index in the total number of as per
        the total number of particles in a renderer. This is used to compute
        for the `base_i` which is the index of this particle's vertex in the
        array of vertices.

    """
    x = 0
    y = 0
    size = 1

    def __init__(self, parent, i):
        self.parent = parent
        self.vsize = parent.vsize
        self.base_i = 4 * i * self.vsize
        self.reset(created=True)

    def reset(self, created=False):
        """ Revert to defaults.


        Parameters
        ----------

        created (bool) - Some particle systems may need a different or
            alternative initialization routine. This flag accounts for such
            behavior.

        """
        raise NotImplementedError()

    def advance(self, nap):
        """ Computes for this particle's new state. Not necessarily showing any
        visible changes.


        Parameters
        ----------

        nap (float) - TODO

        """
        raise NotImplementedError()

    def update(self):
        """ Sync all internal state changes with the vertices array if any.

        """
        for i in range(self.base_i,
                       self.base_i + 4 * self.vsize,
                       self.vsize):
            self.parent.vertices[i:i + 3] = (self.x, self.y, self.size)


class Star(Particle):
    """ The starfield parallax effect

    There will be 3 planes. The stars spawned in the furthest plane will move
    slower than the ones spawned nearest to the player.

    """
    tex_name = 'star'
    plane = 1

    def reset(self, created=False):
        self.plane = randint(1, 3)

        if created:
            self.x = random() * self.parent.width
        else:
            self.x = self.parent.width

        self.y = random() * self.parent.height
        self.size = 0.1 * self.plane

    def advance(self, nap):
        self.x -= 20 * self.plane * nap
        if self.x < 0:
            self.reset()


class Trail(Particle):
    """ The spaceship engine flame

    Spawns near the engine with a randomized size. It then travels away from
    player at a constant speed while shrinking. When it shrinks to 10% or less
    of its size, we reset it.

    """
    tex_name = 'trail'

    def reset(self, created=False):
        self.x = self.parent.player_x + randint(-30, -20)
        self.y = self.parent.player_y + randint(-10, 10)

        if created:
            self.size = 0
        else:
            self.size = random() + 0.6

    def advance(self, nap):
        self.size -= nap
        if self.size <= 0.1:
            self.reset()
        else:
            self.x -= 120 * nap


class Player(Particle):
    """ The player particle just follows the mouse position

    """
    tex_name = 'player'

    def reset(self, created=False):
        self.x = self.parent.player_x
        self.y = self.parent.player_y

    advance = reset


class Bullet(Particle):
    tex_name = 'bullet'
    active = False

    def reset(self, created=False):
        self.active = False
        self.x = -100
        self.y = -100

    def advance(self, nap):
        if self.active:
            self.x += 250 * nap
            if self.x > self.parent.width:
                self.reset()
        elif self.parent.firing and self.parent.fire_delay <= 0:
            self.active = True
            self.x = self.parent.player_x + 40
            self.y = self.parent.player_y
            self.parent.fire_delay += 0.3333


class Enemy(Particle):
    active = False
    tex_name = 'ufo'
    v = 0

    def reset(self, created=False):
        self.active = False
        self.x = -100
        self.y = -100
        v = 0

    def advance(self, nap):
        if self.active:
            # If we're hit, reset.
            if self.check_hit():
                self.reset()
                return

            # Continue moving to the left. When we leave the screen, reset.
            self.x -= 200 * nap
            if self.x < -50:
                self.reset()
                return

            # Move vertically. If we're leaving the view, change the vector
            # sign
            self.y += self.v * nap
            if self.y <= 0:
                self.v = abs(self.v)
            elif self.y > self.parent.height:
                self.v = -abs(self.v)
        elif self.parent.spawn_delay <= 0:
            self.active = True
            self.x = self.parent.width + 50
            self.y = self.parent.height * random()
            self.v = randint(-100, 100)
            self.parent.spawn_delay += 1

    def check_hit(self):

        # Check if we've collide with the player
        if math.hypot(self.parent.player_x - self.x,
                      self.parent.player_y - self.y) < 60:
            return True

        # Check if we've collide with an active bullet
        for b in self.parent.bullets:
            if not b.active:
                continue
            if math.hypot(b.x - self.x, b.y - self.y) < 30:
                b.reset()
                return True


        return False


class Game(PSWidget):

    glsl = 'assets/shaders/shmup.glsl'
    atlas = 'assets/images/shmup.atlas'

    player_x, player_y = Window.mouse_pos
    firing = False
    fire_delay = 0
    spawn_delay = 1

    def __init__(self, **kwargs):
        super(Game, self).__init__(**kwargs)

    def on_touch_down(self, touch):
        self.firing = True
        self.fire_delay = 0
        print('Firing bullets from ({},{})'.format(touch.pos[0], touch.pos[1]))

    def on_touch_up(self, touch):
        self.firing = False

    def initialize(self):
        self.make_particles(Star, 300)
        self.make_particles(Trail, 200)
        self.make_particles(Player, 1)
        self.make_particles(Enemy, 25)
        self.make_particles(Bullet, 25)

        self.bullets = self.particles[-25:]

    def update_glsl(self, nap):
        self.player_x, self.player_y = Window.mouse_pos

        if self.firing:
            self.fire_delay -= nap

        self.spawn_delay -= nap

        super(Game, self).update_glsl(nap)


class GameApp(App):

    def build(self):
        EventLoop.ensure_window()
        return Game()

    def on_start(self):
        self.root.initialize()
        Clock.schedule_interval(self.root.update_glsl, 1 / 60.0)
