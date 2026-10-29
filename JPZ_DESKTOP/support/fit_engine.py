def _value(product, key, default=0):
    try:
        return float(product.get(key, default) or default)
    except (TypeError, ValueError):
        return float(default)

# ระยะเผื่อรอบวงสำหรับคัดเลือกเบื้องต้น ไม่ใช่ผลทดลองใส่หรือค่าความแม่นยำ
EASE = {'baggy': (4, 3), 'wide': (3, 3), 'loose': (3, 2),
        'relaxed': (2, 2), 'straight': (2, 1), 'skinny': (1, .5),
        'flare': (2, 1), 'bootcut': (2, 1), 'cargo': (4, 3), 'wide_straight': (3, 2)}


def fit_details(product, waist, hip, thigh, height, feel='regular'):
    import math
    values = {key: _value(product, key) for key in ('waist', 'hip', 'thigh', 'inseam')}
    if not all(math.isfinite(v) and v > 0 for v in values.values()):
        return None
    hip_ease, thigh_ease = EASE.get(product.get('fit'), (2, 1))
    extra = 1.5 if feel in ('loose', 'relaxed') else 0
    expected = 30 if height < 170 else 31 if height < 178 else 32 if height < 188 else 33
    return {'waist_room': values['waist'] - waist, 'hip_room': values['hip'] - hip,
            'thigh_room': values['thigh'] - thigh, 'hip_ease': hip_ease + extra,
            'thigh_ease': thigh_ease + extra, 'expected_inseam': expected,
            'inseam': values['inseam']}


# J21 | คำนวณทรงยีนส์ที่เหมาะสม
def recommend(products, waist, hip, thigh, height, preferred_fit, feel='regular', length_pref='regular', waist_pref='close'):
    import math
    if not all(math.isfinite(v) and v > 0 for v in (waist, hip, thigh, height)):
        return []
    ranked = []
    for product in products:
        details = fit_details(product, waist, hip, thigh, height, feel)
        if details is None:
            continue
        # ไม่แนะนำเอวเล็กกว่าตัว หรือสะโพก/ต้นขาไม่มีระยะเผื่อตามทรง
        if not (0 <= details['waist_room'] <= 2):
            continue
        if details['hip_room'] < details['hip_ease'] or details['thigh_room'] < details['thigh_ease']:
            continue
        reasons = ['waist', 'hip', 'thigh']
        priority = 7
        if abs(details['inseam'] - details['expected_inseam']) <= 1.5:
            reasons.append('length'); priority += 1
        if product.get('fit') == preferred_fit:
            reasons.append('fit'); priority += 4
        distance = (details['waist_room'] + abs(details['hip_room'] - details['hip_ease']) * .35
                    + abs(details['thigh_room'] - details['thigh_ease']) * .5
                    + abs(details['inseam'] - details['expected_inseam']) * .4)
        ranked.append((priority, -distance, not bool(product.get('estimated', 1)), product, reasons))
    ranked.sort(key=lambda item: item[:3], reverse=True)
    result, seen = [], set()
    for _, __, ___, product, reasons in ranked:
        if product.get('id') in seen:
            continue
        seen.add(product.get('id')); result.append((product, reasons))
        if len(result) == 3:
            break
    return result


def match_jeans(products, waist, thigh, rise, inseam, opening):
    out = []
    for p in products:
        d = abs(_value(p, 'waist') - waist) + abs(_value(p, 'thigh') - thigh) + abs(_value(p, 'rise') - rise) + abs(_value(p, 'inseam') - inseam) + abs(_value(p, 'leg_opening') - opening)
        out.append((d, p))
    result=[];seen=set()
    for distance,p in sorted(out,key=lambda x:x[0]):
        if p.get('id') in seen:continue
        seen.add(p.get('id'));result.append((distance,p))
    return result
