import json

from kivy.app import App
from kivy.core.image import Image
from kivy.graphics import Mesh
from kivy.graphics.instructions import RenderContext
from kivy.uix.widget import Widget


def load_atlas(atlas_name):
    with open(atlas_name, 'rb') as fh:
        atlas = json.loads(fh.read().decode('utf-8'))
        tex_name, mapping = atlas.popitem()

        # We might have to find the abs location of the image if its in a diff.
        # location than this file.
        tex = Image(tex_name).texture
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


class UVMapping(object):
    """ A maintainable way of keeping all coordinate mappings per sprite.

    ---------------------------------------------------------------------------
    Field    | Description
    ---------|-----------------------------------------------------------------
    u0, v0   | UV coordinates of the sprite's top-left corner
    u1, v1   | UV coordinates of the sprite's bottom-right corner
    su       | Sprite width div by 2; useful when building an array of
             | vertices.
    sv       | Sprite height-divided by 2; this similar to the field above.
    ---------------------------------------------------------------------------

    """
    def __init__(self, u0, v0, u1, v1, su, sv):
        self.u0 = u0  #  top left corner
        self.v0 = v0  #  ---
        self.u1 = u1  #  bottom-right corner
        self.v1 = v1  #  ---
        self.su = su  #  equals to 0.5 * width
        self.sv = sv  #  equals to 0.5 * height


class GlslAtlas(Widget):

    def __init__(self, **kwargs):
        super(GlslAtlas, self).__init__(**kwargs)
        self.canvas = RenderContext(use_parent_projection=True)
        self.canvas.shader.source = 'glslatlas.glsl'

        fmt = (
            (b'vCenter', 2, 'float'),
            (b'vPosition', 2, 'float'),
            (b'vTexCoords0', 2, 'float'),
        )

        texture, uvmap = load_atlas('icons.atlas')

        a = uvmap['clock_icon']
        vertices = (
            128, 128, -a.su, -a.sv, a.u0, a.v1,
            128, 128, a.su, -a.sv, a.u1, a.v1,
            128, 128, a.su, a.sv, a.u1, a.v0,
            128, 128, -a.su, a.sv, a.u0, a.v0,
        )
        indices = (
            0, 1, 2,
            2, 3, 0
        )

        b = uvmap['pencil_icon']
        vertices += (
            256, 256, -b.su, -b.sv, b.u0, b.v1,
            256, 256, b.su, -b.sv, b.u1, b.v1,
            256, 256, b.su, b.sv, b.u1, b.v0,
            256, 256, -b.su, b.sv, b.u0, b.v0,
        )
        indices += (
            4, 5, 6,
            6, 7, 4
        )

        with self.canvas:
            Mesh(fmt=fmt, mode='triangles', vertices=vertices, indices=indices,
                 texture=texture)


class GlslAtlasApp(App):

    def build(self):
        return GlslAtlas()


if __name__ == '__main__':
    GlslAtlasApp().run()
