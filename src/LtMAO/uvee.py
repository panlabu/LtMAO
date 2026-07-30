import os, os.path
from . import pyRitoFile

def write_svg(svg_path, uvs, indices):
    with open(svg_path, 'w') as f:
        f.write(f'<svg width="1024" height="1024" xmlns="http://www.w3.org/2000/svg" style="background-color:transparent;">\n')
        for i in range(0, len(indices), 3):
            u1, v1 = uvs[indices[i]]
            u2, v2 = uvs[indices[i+1]]
            u3, v3 = uvs[indices[i+2]]
            f.write(f'<polygon points="{u1*1024},{(1.0-v1)*1024} {u2*1024},{(1.0-v2)*1024} {u3*1024},{(1.0-v3)*1024}" fill="none" stroke="pink" stroke-width="1"/>\n')
        f.write('</svg>')
    print(f'uvee: Finish: Write SVG: {svg_path}')

def uvee_skn(skn_path):
    skn = pyRitoFile.skn.read(skn_path)
    for submesh in skn.submeshes:
        uvs = skn.vertices[4][submesh.vertex_start:submesh.vertex_start+submesh.vertex_count]
        indices = skn.indices[submesh.index_start:submesh.index_start+submesh.index_count]
        min_index = min(indices)
        indices = [index-min_index for index in indices]
        dirname, basename = os.path.split(skn_path)
        svg_path = os.path.join(dirname, f'{submesh.name}.{basename}.svg')
        write_svg(svg_path, uvs, indices)

def uvee_scb(scb_path):
    scb = pyRitoFile.scb.read(scb_path)
    svg_path = scb_path + '.svg'
    write_svg(svg_path, scb.uvs, scb.indices)

def uvee(path):
    if path.endswith('.skn'):
        uvee_skn(path)
    elif path.endswith(('.scb', '.sco')):
        uvee_scb(path)


