import csv
import json
import re
import sys
from collections import Counter
from math import log, sqrt
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "backend" / "data"
DATA_FILE = DATA_DIR / "products.json"
CSV_DATA_FILE = DATA_DIR / "dataset_makeup_fac.csv"
IMAGES_DIR = FRONTEND_DIR / "static" / "images"

BASE_SUBCATEGORIES = ("Cushion", "Foundation", "Skin Tint", "Powder")
ALL_SKIN_TYPES = ("Oily", "Dry", "Combination", "Normal")
RESEARCH_BENEFITS = (
    "Long Lasting",
    "Oil Control",
    "Lightweight",
    "UV Protection",
    "Coverage",
    "Pore Blurring",
    "Waterproof",
    "Hydrating",
)
IMAGE_FIXES = {"ck_j_p.jpeg": "ck_judydoll.jpeg"}
FALLBACK_IMAGE = "placeholder.jpg"

app = Flask(
    __name__,
    template_folder=str(FRONTEND_DIR / "templates"),
    static_folder=str(FRONTEND_DIR / "static"),
    static_url_path="/static",
)


def split_clean(text, sep=","):
    return [value.strip() for value in str(text or "").split(sep) if value.strip()]


def normalize(value):
    return " ".join(str(value or "").strip().lower().split())


def normalize_skin(raw):
    raw = str(raw or "").strip()
    if raw.casefold() in {"all skin type", "all skin types"}:
        return ["All Skin Types"]
    aliases = {"acne prone": "Acne-Prone", "acne-prone": "Acne-Prone"}
    values = raw.replace("&", ",").replace(" Skin", "")
    return [aliases.get(normalize(value), value.strip()) for value in split_clean(values)]


def normalized_benefit_text(value):
    """Merapikan ejaan untuk pencocokan, tanpa mengubah klaim sumber."""
    return normalize(str(value or "").replace("_", " ").replace("-", " "))


def is_long_lasting_claim(keyword):
    """Mencocokkan ketahanan tanpa memasukkan frasa All Day yang tidak relevan."""
    return any((
        "long lasting" in keyword,
        "long wear" in keyword,
        bool(re.search(r"\b\d+\s*h\s*wear\b", keyword)),
        "all day wear" in keyword,
        "lasts all day" in keyword,
    ))


def classify_benefit_claim(value):
    """Mengklasifikasikan satu klaim ke kategori benefit penelitian.

    Teks klaim sumber tidak diubah. Satu klaim dapat masuk lebih dari satu
    kategori, misalnya "SPF 30 PA+++ Lightweight".
    """
    keyword = normalized_benefit_text(value)
    categories = set()
    if is_long_lasting_claim(keyword):
        categories.add("Long Lasting")
    # Shine-Control telah ditetapkan pada tabel normalisasi sebagai Oil Control.
    if "oil control" in keyword or "shine control" in keyword:
        categories.add("Oil Control")
    if "lightweight" in keyword or "weightless" in keyword:
        categories.add("Lightweight")
    if "spf" in keyword or "uv protection" in keyword:
        categories.add("UV Protection")
    # Semua tingkat daya tutup direpresentasikan sebagai satu kategori Coverage.
    if "coverage" in keyword:
        categories.add("Coverage")
    # Porefect Blur juga ditetapkan pada tabel normalisasi sebagai Pore Blurring.
    if "pore blurring" in keyword or "porefect blur" in keyword:
        categories.add("Pore Blurring")
    if "waterproof" in keyword:
        categories.add("Waterproof")
    if "hydrating" in keyword:
        categories.add("Hydrating")
    return categories


def extract_research_benefits(raw):
    """Membentuk delapan kategori CBF dari seluruh klaim benefit produk."""
    found = set()
    for claim in split_clean(raw):
        found.update(classify_benefit_claim(claim))
    return [benefit for benefit in RESEARCH_BENEFITS if benefit in found]
def resolve_image(raw_name):
    fixed_name = IMAGE_FIXES.get(str(raw_name or "").strip(), str(raw_name or "").strip())
    return fixed_name if (IMAGES_DIR / fixed_name).exists() else FALLBACK_IMAGE


def build_products_json():
    """Membentuk katalog Base Makeup dan representasi benefit CBF dari CSV."""
    if not CSV_DATA_FILE.exists():
        raise FileNotFoundError("Dataset CSV tidak ditemukan.")

    with CSV_DATA_FILE.open(encoding="utf-8-sig", newline="") as file:
        rows = csv.DictReader(file, delimiter=";")
        products = []
        seen_product_names = set()
        for row in rows:
            product_name = str(row.get("nama_produk") or "").strip()
            # Nama yang sama dianggap satu produk walau penulisan merek berbeda.
            product_key = normalize(product_name)
            if not product_key or product_key in seen_product_names:
                continue

            sub_category = str(row.get("sub_kategori") or "").strip()
            if sub_category == "Foundition":
                sub_category = "Foundation"
            if sub_category not in BASE_SUBCATEGORIES:
                continue

            seen_product_names.add(product_key)
            original_benefits = split_clean(row.get("benefit"))
            products.append({
                "id": len(products) + 1,
                "name": product_name,
                "brand": str(row.get("brand") or "").strip(),
                "subCategory": sub_category,
                "skinType": ", ".join(normalize_skin(row.get("jenis_kulit"))),
                "finish": ", ".join(split_clean(row.get("finish_type"))),
                # Ditampilkan apa adanya untuk menjaga klaim sumber produk.
                "benefits": ", ".join(original_benefits),
                # Dipakai eksklusif sebagai fitur benefit pada TF-IDF dan cosine similarity.
                "cbfBenefits": ", ".join(extract_research_benefits(row.get("benefit"))),
                "image": resolve_image(row.get("gambar")),
            })

    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(products, file, ensure_ascii=False, indent=2)
    return len(products)


def load_products():
    if not DATA_FILE.exists():
        abort(500, description="File data produk tidak ditemukan.")
    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            products = json.load(file)
    except (OSError, json.JSONDecodeError):
        abort(500, description="File data produk tidak dapat dibaca.")
    if not isinstance(products, list):
        abort(500, description="Format data produk tidak valid.")
    return products


def split_values(value):
    values = value if isinstance(value, list) else str(value or "").split(",")
    return [normalized for item in values if (normalized := normalize(item))]


def add_feature(features, group, value):
    normalized = normalize(value)
    if normalized:
        features.append(f"{group}:{normalized}")


def product_features(product):
    """Profil produk untuk CBF: kulit, finish, dan delapan benefit penelitian."""
    features = []
    skin_types = split_values(product.get("skinType"))
    supports_all_skin = any(value in {"all skin type", "all skin types"} for value in skin_types)
    for value in ALL_SKIN_TYPES if supports_all_skin else skin_types:
        add_feature(features, "skin", value)
    for value in split_values(product.get("finish")):
        add_feature(features, "finish", value)
    for value in split_values(product.get("cbfBenefits")):
        add_feature(features, "benefit", value)
    return features


def preference_features(preferences):
    """Profil query dari preferensi eksplisit pengguna."""
    features = []
    for value in split_values(preferences.get("skinTypes")):
        add_feature(features, "skin", value)
    for value in split_values(preferences.get("finishes")):
        add_feature(features, "finish", value)
    for value in split_values(preferences.get("benefits")):
        add_feature(features, "benefit", value)
    return features


def matches_subcategory(product, preferences):
    selected = set(split_values(preferences.get("subCategories")))
    return bool(selected & set(split_values(product.get("subCategory"))))


def build_idf(products):
    """Menghitung nilai Inverse Document Frequency (IDF) menggunakan rumus ln(N / df)."""

    # DF (Document Frequency): jumlah produk/dokumen yang mengandung setiap fitur.
    document_frequency = Counter()

    for product in products:
        document_frequency.update(set(product_features(product)))

    # N: jumlah seluruh produk/dokumen kandidat.
    document_count = len(products)

    if not document_count:
        return {}

    # IDF: ln(N / DF). Fitur yang jarang muncul memperoleh bobot lebih besar.
    return {
        feature: log(document_count / frequency)
        for feature, frequency in document_frequency.items()
        if frequency > 0
    }


def tf_idf_vector(features, idf, document_count):
    # TF (Term Frequency): jumlah kemunculan setiap fitur dalam satu dokumen/query.
    term_frequency = Counter(features)

    # IDF cadangan untuk fitur query yang tidak ditemukan pada dokumen kandidat.
    fallback_idf = log(document_count) if document_count else 0

    # TF-IDF: TF dikalikan dengan IDF untuk setiap fitur.
    return {feature: frequency * idf.get(feature, fallback_idf) for feature, frequency in term_frequency.items()}


def cosine_similarity(vector_a, vector_b):
    # Pembilang cosine similarity: dot product antara dua vektor TF-IDF.
    dot_product = sum(value * vector_b.get(feature, 0) for feature, value in vector_a.items())

    # Penyebut cosine similarity: panjang/norma Euclidean masing-masing vektor.
    norm_a = sqrt(sum(value ** 2 for value in vector_a.values()))
    norm_b = sqrt(sum(value ** 2 for value in vector_b.values()))

    # Cosine similarity: (A . B) / (||A|| x ||B||).
    return dot_product / (norm_a * norm_b) if norm_a and norm_b else 0


def document_frequencies(products):
    """Menghitung DF fitur pada kandidat, sesuai tahap pembobotan Bab 3."""
    frequencies = Counter()
    for product in products:
        frequencies.update(set(product_features(product)))
    return frequencies


def print_tf_idf_table(title, features, idf, df):
    """Menampilkan TF, DF, IDF, dan TF-IDF untuk dokumentasi pengujian."""
    term_frequency = Counter(features)
    vector = tf_idf_vector(features, idf, 0)
    print("=" * 96)
    print(title)
    print("-" * 96)
    print(f"{'Term':<42}{'TF':>7}{'DF':>7}{'IDF':>14}{'Bobot TF-IDF':>20}")
    print("-" * 96)
    for term in sorted(vector):
        if vector[term]:
            print(f"{term:<42}{term_frequency[term]:>7}{df.get(term, 0):>7}{idf.get(term, 0):>14.6f}{vector[term]:>20.6f}")


def print_calculation_output(query_features, idf, scored_products, document_count):
    """Kompatibilitas mode diagnostik; keluaran rinci tersedia di --test-scenarios."""
    del query_features, idf, scored_products, document_count

def recommend_products(products, preferences, show_calculation=False):
    """Hard filter subkategori, kemudian TF-IDF dan cosine similarity."""
    candidates = [product for product in products if matches_subcategory(product, preferences)]
    if not candidates:
        return []

    document_count = len(candidates)
    idf = build_idf(candidates)
    query_features = preference_features(preferences)
    # Membentuk vektor TF-IDF preferensi pengguna.
    query_vector = tf_idf_vector(query_features, idf, document_count)
    scored_products = []
    for product in candidates:
        # Membentuk vektor TF-IDF untuk setiap produk kandidat.
        product_vector = tf_idf_vector(product_features(product), idf, document_count)

        # Menghitung kemiripan antara preferensi pengguna dan produk.
        similarity = cosine_similarity(query_vector, product_vector)
        if similarity > 0:
            scored_products.append((similarity, product, product_vector))
    scored_products.sort(key=lambda item: (-item[0], normalize(item[1].get("name"))))

    if show_calculation:
        print_calculation_output(query_features, idf, scored_products, document_count)

    # Skor dikirim untuk kebutuhan pengujian, tetapi frontend tidak wajib menampilkannya.
    return [
        {**dict(product), "score": similarity}
        for similarity, product, _ in scored_products
    ]

TEST_SCENARIOS = (
    {"name": "Skenario 1 - Cushion untuk kulit berminyak", "preferences": {"subCategories": ["Cushion"], "skinTypes": ["Oily"], "finishes": ["Matte"], "benefits": ["Long Lasting"]}},
    {"name": "Skenario 2 - Foundation untuk kulit berminyak", "preferences": {"subCategories": ["Foundation"], "skinTypes": ["Oily"], "finishes": ["Matte"], "benefits": ["Oil Control"]}},
    {"name": "Skenario 3 - Skin Tint dengan perlindungan UV", "preferences": {"subCategories": ["Skin Tint"], "skinTypes": ["Oily"], "finishes": ["Natural"], "benefits": ["UV Protection"]}},
    {"name": "Skenario 4 - Powder tahan lama", "preferences": {"subCategories": ["Powder"], "skinTypes": ["Oily"], "finishes": ["Matte"], "benefits": ["Long Lasting"]}},
    {"name": "Skenario 5 - Cushion untuk kulit normal", "preferences": {"subCategories": ["Cushion"], "skinTypes": ["Normal"], "finishes": ["Natural"], "benefits": ["UV Protection"]}},
)


def print_scenario_header(scenario):
    preferences = scenario["preferences"]
    print("\n" + "=" * 76)
    print(f"PENGUJIAN {scenario['name'].upper()}")
    print("=" * 76)
    print(f"Subkategori : {', '.join(preferences['subCategories'])}")
    print(f"Jenis Kulit : {', '.join(preferences['skinTypes'])}")
    print(f"Finish      : {', '.join(preferences['finishes'])}")
    print(f"Benefit     : {', '.join(preferences['benefits'])}")


def print_similarity_table(results):
    print("\nHASIL PERHITUNGAN COSINE SIMILARITY")
    print("-" * 76)
    print(f"{'No':<4}{'Produk':<55}{'Cosine Similarity':>17}")
    print("-" * 76)
    for number, product in enumerate(results, start=1):
        print(f"{number:<4}{product['name'][:53]:<55}{product['score']:>17.6f}")
    print("-" * 76)
    print(f"Total Produk Direkomendasikan: {len(results)}")


def run_test_scenarios():
    """Menjalankan lima skenario tetap untuk dokumentasi pengujian skripsi."""
    products = load_products()
    for number, scenario in enumerate(TEST_SCENARIOS, start=1):
        preferences = scenario["preferences"]
        print_scenario_header(scenario)
        results = recommend_products(products, preferences)
        if number == 1 and results:
            candidates = [product for product in products if matches_subcategory(product, preferences)]
            document_count = len(candidates)
            idf = build_idf(candidates)
            df = document_frequencies(candidates)
            top_product = next(product for product in candidates if product["id"] == results[0]["id"])
            print_tf_idf_table("PEMBOBOTAN TF-IDF PREFERENSI PENGGUNA", preference_features(preferences), idf, df)
            print_tf_idf_table(f"PEMBOBOTAN TF-IDF PRODUK: {top_product['name']}", product_features(top_product), idf, df)
        print_similarity_table(results)

@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/products")
def api_products():
    return jsonify(load_products())


@app.get("/api/products/<subcategory>")
def api_products_by_subcategory(subcategory):
    needle = normalize(subcategory)
    return jsonify([product for product in load_products() if normalize(product.get("subCategory")) == needle])


@app.post("/api/recommendations")
def api_recommendations():
    preferences = request.get_json(silent=True)
    if not isinstance(preferences, dict):
        return jsonify({"error": "Format preferensi tidak valid."}), 400
    preference_fields = ("subCategories", "skinTypes", "finishes", "benefits")
    if any(not isinstance(preferences.get(field, []), list) for field in preference_fields):
        return jsonify({"error": "Setiap preferensi harus berupa daftar."}), 400
    if not preferences.get("subCategories"):
        return jsonify({"error": "Pilih minimal satu subkategori produk."}), 400
    if not any(preferences.get(field) for field in ("skinTypes", "finishes", "benefits")):
        return jsonify({"error": "Pilih minimal satu jenis kulit, hasil akhir/efek, atau kebutuhan makeup."}), 400
    results = recommend_products(load_products(), preferences)
    return jsonify(results)


if __name__ == "__main__":
    if "--build-data" in sys.argv:
        print(f"Wrote {build_products_json()} products to {DATA_FILE}")
    elif "--test-scenarios" in sys.argv:
        run_test_scenarios()
    else:
        app.run(debug=True, host="0.0.0.0", port=5000)








