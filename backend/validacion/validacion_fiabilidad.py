import json
import os
from Levenshtein import ratio as lev_ratio

def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def find_matching_segment(gt_list, collected_data):
    """Asocia un JSON de resultados con un segmento de ground truth basado en numero_tractor y eta."""
    collected_fields = {
        **collected_data.get('driver_details', {}),
        **collected_data.get('tractor_details', {}),
        **collected_data.get('trailer_details', {}),
        **collected_data.get('eta_details', {})
    }
    collected_tractor = collected_fields.get('numero_tractor', '')
    collected_eta = collected_fields.get('eta', '')

    best_match = None
    best_score = 0
    for gt in gt_list:
        gt_fields = gt.get('fields', {})
        score = (
            lev_ratio(str(gt_fields.get('numero_tractor', '')), str(collected_tractor)) * 0.6 +
            lev_ratio(str(gt_fields.get('eta', '')), str(collected_eta)) * 0.4
        )
        if score > best_score:
            best_score = score
            best_match = gt

    if best_match:
        return best_match['segment'], best_match['route']
    return None, None
    #return best_match['segment'], best_match['route'] if best_match else (None, None)

# Cargar ground truth
gt_list = load_json('ground_truth.json')

# Directorio con los JSON de resultados
results_dir = 'conversation_logs'
results = []

# Campos a evaluar
field_names = [
    "nombre_operador", "numero_tractor", "placa_tractor",
    "numero_trailer", "placa_trailer", "eta"
]

# Procesar cada archivo JSON en la carpeta results/
for filename in os.listdir(results_dir):
    if filename.endswith('.json'):
        file_path = os.path.join(results_dir, filename)
        collected_data = load_json(file_path)

        # Extraer campos de los resultados
        collected_fields = {
            **collected_data.get('driver_details', {}),
            **collected_data.get('tractor_details', {}),
            **collected_data.get('trailer_details', {}),
            **collected_data.get('eta_details', {})
        }

        # Encontrar el segmento correspondiente en ground truth
        segment, route = find_matching_segment(gt_list, collected_data)
        if segment is None:
            print(f"Advertencia: No se encontró coincidencia para {filename}")
            continue

        # Obtener los campos de ground truth para este segmento
        gt_fields = next((gt['fields'] for gt in gt_list if gt['segment'] == segment), {})

        n_exp = len(field_names)

        # 1) Completeness
        detected = [f for f in field_names if collected_fields.get(f) not in (None, "")]
        completeness = 100 * len(detected) / n_exp if n_exp else 0

        # 2) Levenshtein ratio promedio
        sum_ratios = sum(
            lev_ratio(str(gt_fields.get(field, "")), str(collected_fields.get(field, "")))
            for field in field_names
        )
        avg_lev_ratio = sum_ratios / n_exp if n_exp else 0

        # 3) Exact Match Percentage
        exact_count = sum(
            1 for field in field_names
            if str(gt_fields.get(field, "")).strip() == str(collected_fields.get(field, "")).strip()
        )
        exact_pct = 100 * exact_count / n_exp if n_exp else 0

        # Detalle de errores por campo
        errors = {
            field: {
                "ground_truth": gt_fields.get(field, ""),
                "collected": collected_fields.get(field, ""),
                "lev_ratio": round(lev_ratio(str(gt_fields.get(field, "")), str(collected_fields.get(field, ""))), 3),
                "exact_match": str(gt_fields.get(field, "")).strip() == str(collected_fields.get(field, "")).strip()
            }
            for field in field_names
        }

        results.append({
            "filename": filename,
            "segment": segment,
            "route": route,
            "exact_match_pct": round(exact_pct, 1),
            "levenshtein_ratio": round(avg_lev_ratio, 3),
            "completeness_pct": round(completeness, 1),
            "field_errors": errors
        })

# Guardar resultados
with open('reliability_metrics.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# Resumen en consola
for r in results:
    print(f"\nArchivo: {r['filename']} [Seg {r['segment']}]")
    print(f"Exact%={r['exact_match_pct']} %, Lev={r['levenshtein_ratio']}, Compl={r['completeness_pct']} %")
    print("Errores por campo:")
    for field, info in r['field_errors'].items():
        if not info['exact_match']:
            print(f"  {field}: GT='{info['ground_truth']}', Collected='{info['collected']}', Lev={info['lev_ratio']}")