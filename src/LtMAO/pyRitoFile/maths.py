from math import sqrt, acos, sin

try:
    from xxhash import xxh64_intdigest, xxh3_64_intdigest as hash_xxh3_64
except:
    print('Warning: pyRitoFile.maths failed to import xxhash.')

def hash_elf(s):
    h = 0
    m = 0xF0000000
    for b in s.encode().lower():
        h = (h << 4) + b
        t = h & m
        if t:
            h ^= t >> 24
            h &= ~t
    return h

def hash_fnv1a(s):
    h = 0x811c9dc5
    p = 0x01000193
    m = 0xFFFFFFFF
    for b in s.encode().lower():
        h = (h ^ b) * p & m
    return h

def hash_fnv1(s):
    h = 0x811c9dc5
    p = 0x01000193
    m = 0xFFFFFFFF
    for b in s.encode().lower():
        h = h * p & m ^ b
    return h

def hash_xxh64(s):
    return xxh64_intdigest(s.lower())

def vector3_lerp(a, b, weight):   
    x1, y1, z1 = a
    x2, y2, z2 = b
    return (
        x1 + (x2 - x1) * weight,
        y1 + (y2 - y1) * weight,
        z1 + (z2 - z1) * weight
    )

def quaternion_slerp(a, b, weight):
    x1, y1, z1, w1 = a
    x2, y2, z2, w2 = b
    cos_omega = x1 * x2 + y1 * y2 + z1 * z2 + w1 * w2
    flip = 1.0
    if cos_omega < 0.0:
        flip = -1.0
        cos_omega = -cos_omega
    if cos_omega > 0.9995:
        s1 = 1.0 - weight
        s2 = weight * flip
    else:
        omega = acos(cos_omega)
        inv_sin_omega = 1 / sin(omega)
        s1 = sin((1.0 - weight) * omega) * inv_sin_omega
        s2 = sin(weight * omega) * inv_sin_omega * flip
    return (
        s1 * x1 + s2 * x2,
        s1 * y1 + s2 * y2,
        s1 * z1 + s2 * z2,
        s1 * w1 + s2 * w2,
    ) 

def quaternion_compress(quat):
    abs_quat = [abs(v) for v in quat]
    max_index = abs_quat.index(max(abs_quat))
    if quat[max_index] < 0:
        quat = [-v for v in quat]
    bits = max_index << 45
    s = 1.41421356237 # sqrt(2)
    c = 0
    for i, v in enumerate(quat):
        if i != max_index:
            bits |= (round(16383.5 * (s * v + 1.0)) & 32767) << (30 - 15 * c)
            c += 1
    return bits.to_bytes(6, 'little')

def quaternion_decompress(quat_bytes):
    bits = int.from_bytes(quat_bytes, 'little')
    t = 32767 # 2^15-1
    s = 0.00004315969 # sqrt(2)/t
    o = 0.70710678118 # 1/sqrt(2)
    c = (bits & t) * s - o
    b = (bits >> 15 & t) * s - o
    a = (bits >> 30 & t) * s - o
    d = sqrt(max(0.0, 1.0 - (a * a + b * b + c * c)))
    return (
        (d, a, b, c),
        (a, d, b, c),
        (a, b, d, c),
        (a, b, c, d)
    )[bits >> 45 & 3]

def matrix4_multiply(a, b):
    a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14, a15 = a
    b0, b1, b2, b3, b4, b5, b6, b7, b8, b9, b10, b11, b12, b13, b14, b15 = b

    return (
        a0*b0 + a1*b4 + a2*b8 + a3*b12,
        a0*b1 + a1*b5 + a2*b9 + a3*b13,
        a0*b2 + a1*b6 + a2*b10 + a3*b14,
        a0*b3 + a1*b7 + a2*b11 + a3*b15,
    
        a4*b0 + a5*b4 + a6*b8 + a7*b12,
        a4*b1 + a5*b5 + a6*b9 + a7*b13,
        a4*b2 + a5*b6 + a6*b10 + a7*b14,
        a4*b3 + a5*b7 + a6*b11 + a7*b15,
        
        a8*b0 + a9*b4 + a10*b8 + a11*b12,
        a8*b1 + a9*b5 + a10*b9 + a11*b13,
        a8*b2 + a9*b6 + a10*b10 + a11*b14,
        a8*b3 + a9*b7 + a10*b11 + a11*b15,
        
        a12*b0 + a13*b4 + a14*b8 + a15*b12,
        a12*b1 + a13*b5 + a14*b9 + a15*b13,
        a12*b2 + a13*b6 + a14*b10 + a15*b14,
        a12*b3 + a13*b7 + a14*b11 + a15*b15
    )


def matrix4_inverse(m):
    m0, m1, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12, m13, m14, m15 = m

    inv0 = m5 * m10 * m15 - m5 * m11 * m14 - m9 * m6 * m15 + m9 * m7 * m14 + m13 * m6 * m11 - m13 * m7 * m10
    inv4 = -m4 * m10 * m15 + m4 * m11 * m14 + m8 * m6 * m15 - m8 * m7 * m14 - m12 * m6 * m11 + m12 * m7 * m10
    inv8 = m4 * m9 * m15 - m4 * m11 * m13 - m8 * m5 * m15 + m8 * m7 * m13 + m12 * m5 * m11 - m12 * m7 * m9
    inv12 = -m4 * m9 * m14 + m4 * m10 * m13 + m8 * m5 * m14 - m8 * m6 * m13 - m12 * m5 * m10 + m12 * m6 * m9

    det = m0 * inv0 + m1 * inv4 + m2 * inv8 + m3 * inv12
    if det == 0:
        raise Exception(f'pyRitoFile: Error: Singular matrix: {m}')
    det_inv = 1.0 / det

    return (
        inv0 * det_inv,
        (-m1 * m10 * m15 + m1 * m11 * m14 + m9 * m2 * m15 - m9 * m3 * m14 - m13 * m2 * m11 + m13 * m3 * m10) * det_inv,
        (m1 * m6 * m15 - m1 * m7 * m14 - m5 * m2 * m15 + m5 * m3 * m14 + m13 * m2 * m7 - m13 * m3 * m6) * det_inv,
        (-m1 * m6 * m11 + m1 * m7 * m10 + m5 * m2 * m11 - m5 * m3 * m10 - m9 * m2 * m7 + m9 * m3 * m6) * det_inv,
        inv4 * det_inv,
        (m0 * m10 * m15 - m0 * m11 * m14 - m8 * m2 * m15 + m8 * m3 * m14 + m12 * m2 * m11 - m12 * m3 * m10) * det_inv,
        (-m0 * m6 * m15 + m0 * m7 * m14 + m4 * m2 * m15 - m4 * m3 * m14 - m12 * m2 * m7 + m12 * m3 * m6) * det_inv,
        (m0 * m6 * m11 - m0 * m7 * m10 - m4 * m2 * m11 + m4 * m3 * m10 + m8 * m2 * m7 - m8 * m3 * m6) * det_inv,
        inv8 * det_inv,
        (-m0 * m9 * m15 + m0 * m11 * m13 + m8 * m1 * m15 - m8 * m3 * m13 - m12 * m1 * m11 + m12 * m3 * m9) * det_inv,
        (m0 * m5 * m15 - m0 * m7 * m13 - m4 * m1 * m15 + m4 * m3 * m13 + m12 * m1 * m7  - m12 * m3 * m5) * det_inv,
        (-m0 * m5 * m11 + m0 * m7 * m9 + m4 * m1 * m11 - m4 * m3 * m9 - m8 * m1 * m7 + m8 * m3 * m5) * det_inv,
        inv12 * det_inv,
        (m0 * m9 * m14 - m0 * m10 * m13 - m8 * m1 * m14 + m8 * m2 * m13 + m12 * m1 * m10 - m12 * m2 * m9) * det_inv,
        (-m0 * m5 * m14 + m0 * m6 * m13 + m4 * m1 * m14 - m4 * m2 * m13 - m12 * m1 * m6 + m12 * m2 * m5) * det_inv,
        (m0 * m5 * m10 - m0 * m6 * m9 - m4 * m1 * m10 + m4 * m2 * m9 + m8 * m1 * m6 - m8 * m2 * m5) * det_inv
    )

def matrix4_decompose(m):
    # translate
    tx, ty, tz = m[3], m[7], m[11]
    
    # scale
    sx = sqrt(m[0]**2 + m[4]**2 + m[8]**2)
    sy = sqrt(m[1]**2 + m[5]**2 + m[9]**2)
    sz = sqrt(m[2]**2 + m[6]**2 + m[10]**2)
    
    # division by zero 
    if sx == 0 or sy == 0 or sz == 0:
        return (tx, ty, tz), (0.0, 0.0, 0.0, 1.0), (sx, sy, sz)

    # remove scale out to get rotate matrix
    m00, m01, m02 = m[0]/sx, m[1]/sy, m[2]/sz
    m10, m11, m12 = m[4]/sx, m[5]/sy, m[6]/sz
    m20, m21, m22 = m[8]/sx, m[9]/sy, m[10]/sz
    
    # get quat from rotate matrix
    trace = m00 + m11 + m22
    if trace > 0:
        s = sqrt(trace + 1.0) * 2
        qw = 0.25 * s
        qx = (m21 - m12) / s
        qy = (m02 - m20) / s
        qz = (m10 - m01) / s
    elif (m00 > m11) and (m00 > m22):
        s = sqrt(1.0 + m00 - m11 - m22) * 2
        qw = (m21 - m12) / s
        qx = 0.25 * s
        qy = (m01 + m10) / s
        qz = (m02 + m20) / s
    elif m11 > m22:
        s = sqrt(1.0 + m11 - m00 - m22) * 2
        qw = (m02 - m20) / s
        qx = (m01 + m10) / s
        qy = 0.25 * s
        qz = (m12 + m21) / s
    else:
        s = sqrt(1.0 + m22 - m00 - m11) * 2
        qw = (m10 - m01) / s
        qx = (m02 + m20) / s
        qy = (m12 + m21) / s
        qz = 0.25 * s
        
    return (tx, ty, tz), (qx, qy, qz, qw), (sx, sy, sz)

